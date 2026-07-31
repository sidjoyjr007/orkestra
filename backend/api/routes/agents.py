import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token, require_permission
from backend.api.services.agent_service import AgentService

router = APIRouter()

class AgentCreateUpdate(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    system_prompt: str
    llm: str
    llmProvider: str
    selectedTools: List[str]
    selectedMcps: List[str]
    selectedGuardrails: List[str]
    max_iterations: Optional[int] = 20
    compaction_tokens: Optional[int] = 30000
    allowed_roles: Optional[List[str]] = []
    is_public: Optional[bool] = False

def get_agent_service(db: AsyncSession = Depends(get_db)) -> AgentService:
    return AgentService(db)

@router.get("")
async def list_agents(
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("agents:read")),
    service: AgentService = Depends(get_agent_service)
):
    return await service.list_agents(
        user_id=user["sub"],
        role=user.get("role", "VIEWER"),
        limit=limit,
        offset=offset,
        q=q
    )

@router.post("")
async def create_agent(
    payload: AgentCreateUpdate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("agents:create")),
    service: AgentService = Depends(get_agent_service)
):
    agent_id = await service.create_agent(payload.model_dump(), user["sub"])
    return {"message": "Agent created successfully", "id": agent_id}

@router.put("/{agent_id}")
async def update_agent(
    agent_id: str,
    payload: AgentCreateUpdate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("agents:edit")),
    service: AgentService = Depends(get_agent_service)
):
    try:
        await service.update_agent(
            agent_id=agent_id,
            payload_dict=payload.model_dump(),
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
        return {"message": "Agent updated successfully", "id": agent_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.delete("/{agent_id}")
async def delete_agent(
    agent_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("agents:delete")),
    service: AgentService = Depends(get_agent_service)
):
    try:
        await service.delete_agent(
            agent_id=agent_id,
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
