from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional, Any, Dict
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token, require_permission
from backend.api.services.tool_service import ToolService

router = APIRouter()

class ToolParam(BaseModel):
    name: str
    description: str
    type: str
    default: str
    required: bool

class EnvVar(BaseModel):
    key: str
    value: str

class ToolCreateUpdate(BaseModel):
    id: Optional[str] = None
    name: str
    desc: str
    params: List[ToolParam]
    script: str
    envVars: List[EnvVar]
    tool_type: str = "SANDBOX"
    is_public: bool = False
    requires_approval: bool = False
    network_access: bool = False
    status: str = "DRAFT"
    allowed_roles: Optional[List[str]] = []

class ToolExecutePayload(BaseModel):
    parameters: Dict[str, Any] = {}

def get_tool_service(db: AsyncSession = Depends(get_db)) -> ToolService:
    return ToolService(db)

@router.get("")
async def list_tools(
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("tools:read")),
    service: ToolService = Depends(get_tool_service)
):
    return await service.list_tools(
        user_id=user["sub"],
        role=user.get("role", "VIEWER"),
        limit=limit,
        offset=offset,
        q=q
    )

@router.post("")
async def create_or_update_tool(
    payload: ToolCreateUpdate,
    user: dict = Depends(get_current_user_token),
    service: ToolService = Depends(get_tool_service)
):
    try:
        payload_dict = payload.model_dump()
        user_permissions = user.get("permissions", [])
        tool_id = await service.save_tool(
            payload_dict=payload_dict,
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER"),
            user_permissions=user_permissions
        )
        return {"message": "Tool saved successfully", "id": tool_id}
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.delete("/{tool_id}")
async def delete_tool(
    tool_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("tools:delete")),
    service: ToolService = Depends(get_tool_service)
):
    try:
        await service.delete_tool(
            tool_id=tool_id,
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
        return {"status": "deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.post("/{tool_id}/execute")
async def execute_tool(
    tool_id: str,
    payload: ToolExecutePayload,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("tools:execute")),
    service: ToolService = Depends(get_tool_service)
):
    try:
        return await service.execute_tool(
            tool_id=tool_id,
            parameters=payload.parameters,
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
