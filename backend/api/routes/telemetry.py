import uuid
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from datetime import datetime
from sqlalchemy import func

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token
from backend.api.models.telemetry import AgentRun, RunEvent

router = APIRouter()

class TelemetryEventPayload(BaseModel):
    agent_id: str
    session_id: str
    event_type: str
    details: Dict[str, Any]

@router.post("/events")
async def ingest_telemetry_event(
    payload: TelemetryEventPayload,
    db: AsyncSession = Depends(get_db)
    # Note: For strict security, we should validate a telemetry token here, 
    # but for simplicity we rely on network isolation.
):
    # Upsert the AgentRun
    run_result = await db.execute(
        select(AgentRun).where(
            AgentRun.agent_id == payload.agent_id,
            AgentRun.session_id == payload.session_id
        )
    )
    run = run_result.scalars().first()
    
    if not run:
        run = AgentRun(
            agent_id=payload.agent_id,
            session_id=payload.session_id,
            status="IN_PROGRESS"
        )
        db.add(run)
        await db.commit()
        await db.refresh(run)
        
    # Create the RunEvent
    event = RunEvent(
        run_id=run.id,
        event_type=payload.event_type,
        details=payload.details
    )
    db.add(event)
    
    # Update AgentRun totals if applicable
    if payload.event_type == "TokenUsageReported":
        p_tok = payload.details.get("prompt_tokens", 0)
        c_tok = payload.details.get("completion_tokens", 0)
        t_tok = payload.details.get("total_tokens", 0)
        if not t_tok:
            t_tok = p_tok + c_tok
            
        run.prompt_tokens += p_tok
        run.completion_tokens += c_tok
        run.total_tokens += t_tok
        
    if payload.event_type == "AgentStepCompleted":
        run.status = "COMPLETED"
        run.end_time = datetime.utcnow()
        
    if payload.event_type == "AgentStepFailed":
        run.status = "FAILED"
        run.end_time = datetime.utcnow()

    await db.commit()
    return {"status": "accepted"}

@router.get("/runs")
async def list_runs(
    limit: int = 50,
    offset: int = 0,
    agent_id: Optional[str] = None,
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    query = select(AgentRun)
    if agent_id:
        query = query.where(AgentRun.agent_id == agent_id)
        
    query = query.order_by(AgentRun.start_time.desc()).limit(limit).offset(offset)
    result = await db.execute(query)
    runs = result.scalars().all()
    
    return {
        "items": [
            {
                "id": str(r.id),
                "agent_id": r.agent_id,
                "session_id": r.session_id,
                "status": r.status,
                "start_time": r.start_time.isoformat(),
                "end_time": r.end_time.isoformat() if r.end_time else None,
                "total_tokens": r.total_tokens
            } for r in runs
        ],
        "total": len(runs)
    }

@router.get("/stats")
async def get_agent_stats(
    agent_id: str,
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    runs_query = select(func.count(AgentRun.id)).where(AgentRun.agent_id == agent_id)
    runs_result = await db.execute(runs_query)
    total_runs = runs_result.scalar() or 0
    
    active_query = select(func.count(AgentRun.id)).where(AgentRun.agent_id == agent_id, AgentRun.status == "IN_PROGRESS")
    active_result = await db.execute(active_query)
    active_executions = active_result.scalar() or 0
    
    tokens_query = select(func.sum(AgentRun.total_tokens)).where(AgentRun.agent_id == agent_id)
    tokens_result = await db.execute(tokens_query)
    total_tokens = tokens_result.scalar() or 0
    
    return {
        "total_runs": total_runs,
        "active_executions": active_executions,
        "total_tokens": total_tokens
    }

@router.get("/runs/{run_id}/events")
async def get_run_events(
    run_id: str,
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    query = select(RunEvent).where(RunEvent.run_id == run_id).order_by(RunEvent.timestamp.asc())
    result = await db.execute(query)
    events = result.scalars().all()
    
    return [
        {
            "id": str(e.id),
            "event_type": e.event_type,
            "timestamp": e.timestamp.isoformat(),
            "details": e.details
        } for e in events
    ]
