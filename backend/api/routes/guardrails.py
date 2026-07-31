from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token, require_permission
from backend.api.services.guardrail_service import GuardrailService

router = APIRouter()

class GuardrailCreateUpdate(BaseModel):
    id: Optional[str] = None
    name: str
    description: str
    stage: str
    action: str
    handlerType: str
    rules: str
    allowed_roles: Optional[List[str]] = []
    is_public: Optional[bool] = False

def get_guardrail_service(db: AsyncSession = Depends(get_db)) -> GuardrailService:
    return GuardrailService(db)

@router.get("")
async def list_guardrails(
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("guardrails:read")),
    service: GuardrailService = Depends(get_guardrail_service)
):
    return await service.list_guardrails(
        user_id=user["sub"],
        user_role=user.get("role", "VIEWER"),
        limit=limit,
        offset=offset,
        q=q
    )

@router.post("")
async def create_guardrail(
    payload: GuardrailCreateUpdate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("guardrails:create")),
    service: GuardrailService = Depends(get_guardrail_service)
):
    try:
        new_id = await service.create_guardrail(payload.model_dump(), user["sub"])
        return {"message": "Guardrail created successfully", "id": new_id}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.get("/{guardrail_id}")
async def get_guardrail(
    guardrail_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("guardrails:read")),
    service: GuardrailService = Depends(get_guardrail_service)
):
    try:
        return await service.get_guardrail(
            guardrail_id=guardrail_id,
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.put("/{guardrail_id}")
async def update_guardrail(
    guardrail_id: str,
    payload: GuardrailCreateUpdate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("guardrails:edit")),
    service: GuardrailService = Depends(get_guardrail_service)
):
    try:
        await service.update_guardrail(
            guardrail_id=guardrail_id,
            payload_dict=payload.model_dump(),
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
        return {"message": "Guardrail updated successfully"}
    except ValueError as e:
        if "not found" in str(e).lower():
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

@router.delete("/{guardrail_id}")
async def delete_guardrail(
    guardrail_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("guardrails:delete")),
    service: GuardrailService = Depends(get_guardrail_service)
):
    try:
        await service.delete_guardrail(guardrail_id)
        return {"message": "Guardrail deleted successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
