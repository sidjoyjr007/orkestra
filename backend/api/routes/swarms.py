from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid

from backend.api.core.database import get_db
from backend.api.models.swarm import Swarm, SwarmAgent
from backend.api.models.agent import AgentConfig

router = APIRouter()

class SwarmAgentCreate(BaseModel):
    agent_id: str
    role_description: Optional[str] = None

class SwarmCreate(BaseModel):
    name: str
    description: Optional[str] = None
    leader_agent_id: str
    subagents: List[SwarmAgentCreate] = []

class SwarmAgentResponse(BaseModel):
    agent_id: str
    role_description: Optional[str]

class SwarmResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    leader_agent_id: str
    created_at: str
    subagents: List[SwarmAgentResponse] = []
    
    class Config:
        from_attributes = True

@router.get("/", response_model=List[SwarmResponse])
async def get_swarms(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Swarm).options(selectinload(Swarm.subagents)))
    swarms = result.scalars().all()
    
    out = []
    for s in swarms:
        out.append(SwarmResponse(
            id=str(s.id),
            name=s.name,
            description=s.description,
            leader_agent_id=str(s.leader_agent_id),
            created_at=s.created_at.isoformat(),
            subagents=[SwarmAgentResponse(agent_id=str(sa.agent_id), role_description=sa.role_description) for sa in s.subagents]
        ))
    return out

@router.post("/", response_model=SwarmResponse)
async def create_swarm(swarm: SwarmCreate, db: AsyncSession = Depends(get_db)):
    # Validate leader exists
    leader = await db.execute(select(AgentConfig).where(AgentConfig.id == swarm.leader_agent_id))
    if not leader.scalars().first():
        raise HTTPException(status_code=404, detail="Leader agent not found")
        
    db_swarm = Swarm(
        name=swarm.name,
        description=swarm.description,
        leader_agent_id=swarm.leader_agent_id
    )
    db.add(db_swarm)
    await db.flush() # get ID
    
    for sa in swarm.subagents:
        agent = await db.execute(select(AgentConfig).where(AgentConfig.id == sa.agent_id))
        if not agent.scalars().first():
            raise HTTPException(status_code=404, detail=f"Subagent {sa.agent_id} not found")
            
        db_sa = SwarmAgent(
            swarm_id=db_swarm.id,
            agent_id=sa.agent_id,
            role_description=sa.role_description
        )
        db.add(db_sa)
        
    await db.commit()
    await db.refresh(db_swarm)
    
    return SwarmResponse(
        id=str(db_swarm.id),
        name=db_swarm.name,
        description=db_swarm.description,
        leader_agent_id=str(db_swarm.leader_agent_id),
        created_at=db_swarm.created_at.isoformat(),
        subagents=[SwarmAgentResponse(agent_id=str(sa.agent_id), role_description=sa.role_description) for sa in swarm.subagents]
    )

@router.delete("/{swarm_id}")
async def delete_swarm(swarm_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Swarm).where(Swarm.id == swarm_id))
    swarm = result.scalars().first()
    if not swarm:
        raise HTTPException(status_code=404, detail="Swarm not found")
        
    await db.delete(swarm)
    await db.commit()
    return {"message": "Swarm deleted successfully"}

@router.put("/{swarm_id}", response_model=SwarmResponse)
async def update_swarm(swarm_id: str, swarm_update: SwarmCreate, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Swarm).options(selectinload(Swarm.subagents)).where(Swarm.id == swarm_id))
    swarm = result.scalars().first()
    if not swarm:
        raise HTTPException(status_code=404, detail="Swarm not found")

    leader = await db.execute(select(AgentConfig).where(AgentConfig.id == swarm_update.leader_agent_id))
    if not leader.scalars().first():
        raise HTTPException(status_code=404, detail="Leader agent not found")

    swarm.name = swarm_update.name
    swarm.description = swarm_update.description
    swarm.leader_agent_id = swarm_update.leader_agent_id

    # Delete existing subagents
    for sa in swarm.subagents:
        await db.delete(sa)
    
    # Add new subagents
    for sa in swarm_update.subagents:
        agent = await db.execute(select(AgentConfig).where(AgentConfig.id == sa.agent_id))
        if not agent.scalars().first():
            raise HTTPException(status_code=404, detail=f"Subagent {sa.agent_id} not found")
        db_sa = SwarmAgent(
            swarm_id=swarm.id,
            agent_id=sa.agent_id,
            role_description=sa.role_description
        )
        db.add(db_sa)

    await db.commit()
    await db.refresh(swarm)
    
    return SwarmResponse(
        id=str(swarm.id),
        name=swarm.name,
        description=swarm.description,
        leader_agent_id=str(swarm.leader_agent_id),
        created_at=swarm.created_at.isoformat(),
        subagents=[SwarmAgentResponse(agent_id=str(sa.agent_id), role_description=sa.role_description) for sa in swarm_update.subagents]
    )
