from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import Any, Optional
from datetime import datetime
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
import httpx
import os

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token
from backend.api.models.hitl import HitlSession
from backend.api.models.deployment import AgentDeployment

router = APIRouter()

class HitlResponsePayload(BaseModel):
    action: str  # "APPROVE", "REJECT", or "RESPOND"
    response_text: Optional[str] = None
    
@router.post("/{hitl_id}/respond")
async def respond_to_hitl(
    hitl_id: str,
    payload: HitlResponsePayload,
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    # Find the HITL session
    result = await db.execute(select(HitlSession).where(HitlSession.id == hitl_id))
    hitl = result.scalars().first()
    
    if not hitl:
        raise HTTPException(status_code=404, detail="HITL session not found")
        
    if hitl.status != "PENDING":
        raise HTTPException(status_code=400, detail=f"HITL session is already resolved ({hitl.status})")
        
    # Mark resolved in DB
    if payload.action == "APPROVE":
        hitl.status = "APPROVED"
    elif payload.action == "REJECT":
        hitl.status = "REJECTED"
    else:
        hitl.status = "RESPONDED"
        
    hitl.resolved_at = datetime.utcnow()
    await db.commit()
    
    # We directly inject the human response into the agent's memory in PostgreSQL.
    # The frontend can then resume the agent by issuing a new /chat or /chat/stream request.
    if hitl.request_type == "TOOL_APPROVAL":
        if payload.action == "APPROVE":
            # Inject a system flag so the runner knows to bypass the approval check when it resumes.
            msg_role = "system"
            msg_content = f"[HITL_APPROVED] {hitl.context.get('tool_call_id')}"
            msg_name = None
            msg_tool_call_id = None
        else:
            # If rejected, we inject the tool response so it stops trying to execute it.
            msg_role = "tool"
            msg_content = payload.response_text or "Human rejected this action."
            msg_name = hitl.context.get("tool_name")
            msg_tool_call_id = hitl.context.get("tool_call_id")
    else:
        msg_role = "user"
        msg_content = payload.response_text or ""
        msg_name = None
        msg_tool_call_id = None
        
    from sqlalchemy import text
    await db.execute(
        text("INSERT INTO orkestra_messages (session_id, role, content, name, tool_call_id) VALUES (:session_id, :role, :content, :name, :tool_call_id)"),
        {
            "session_id": hitl.session_id,
            "role": msg_role,
            "content": msg_content,
            "name": msg_name,
            "tool_call_id": msg_tool_call_id
        }
    )
    await db.commit()
    
    return {"status": "success", "message": "Response recorded. Agent is ready to resume."}
