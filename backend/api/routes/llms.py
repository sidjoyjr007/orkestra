from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
import httpx

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token, require_permission
from backend.api.services.llm_service import LlmService

router = APIRouter()

class LlmConfigCreate(BaseModel):
    name: str
    provider: str
    model_name: str
    endpoint_url: Optional[str] = None
    headers: Optional[dict] = None
    api_key: Optional[str] = None
    allowed_roles: Optional[List[str]] = []
    is_public: Optional[bool] = False

class LlmConfigResponse(BaseModel):
    id: str
    name: str
    provider: str
    model_name: str
    endpoint_url: Optional[str] = None
    headers: Optional[dict] = None
    has_api_key: bool
    allowed_roles: List[str]
    is_public: bool
    creator_id: str
    
    class Config:
        from_attributes = True

class LlmTestRequest(BaseModel):
    prompt: str

def get_llm_service(db: AsyncSession = Depends(get_db)) -> LlmService:
    return LlmService(db)

@router.get("", response_model=List[LlmConfigResponse])
async def list_llms(
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("llms:read")),
    service: LlmService = Depends(get_llm_service)
):
    return await service.list_llms(
        user_id=user["sub"],
        user_role=user.get("role", "VIEWER")
    )

@router.post("", response_model=LlmConfigResponse)
async def create_llm(
    payload: LlmConfigCreate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("llms:create")),
    service: LlmService = Depends(get_llm_service)
):
    return await service.create_llm(payload.model_dump(), user["sub"])

@router.put("/{llm_id}", response_model=LlmConfigResponse)
async def update_llm(
    llm_id: str,
    payload: LlmConfigCreate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("llms:edit")),
    service: LlmService = Depends(get_llm_service)
):
    try:
        return await service.update_llm(
            llm_id=llm_id,
            payload_dict=payload.model_dump(),
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.delete("/{llm_id}")
async def delete_llm(
    llm_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("llms:delete")),
    service: LlmService = Depends(get_llm_service)
):
    try:
        await service.delete_llm(
            llm_id=llm_id,
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
        return {"message": "LLM configuration deleted"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))

@router.post("/{llm_id}/test")
async def test_llm(
    llm_id: str,
    payload: LlmTestRequest,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("llms:read")),
    service: LlmService = Depends(get_llm_service)
):
    try:
        return await service.test_llm(
            llm_id=llm_id,
            prompt=payload.prompt,
            user_id=user["sub"],
            user_role=user.get("role", "VIEWER")
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Provider API error: {e.response.text}")
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Internal error communicating with provider: {str(e)}")
