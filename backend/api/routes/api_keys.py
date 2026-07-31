import uuid
import hashlib
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from datetime import datetime

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token
from backend.api.models.api_key import ApiKey

router = APIRouter()

class ApiKeyCreate(BaseModel):
    name: str

class ApiKeyResponse(BaseModel):
    id: str
    name: str
    prefix: str
    is_active: bool
    created_at: str
    
    # Only returned on creation
    raw_key: Optional[str] = None

@router.get("/", response_model=List[ApiKeyResponse])
async def list_api_keys(
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ApiKey).where(ApiKey.creator_id == user["sub"]))
    keys = result.scalars().all()
    return [ApiKeyResponse(**k.to_dict()) for k in keys]

@router.post("/", response_model=ApiKeyResponse)
async def create_api_key(
    payload: ApiKeyCreate,
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    # Generate a new random API key
    raw_key = f"ork_{uuid.uuid4().hex}{uuid.uuid4().hex}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    
    api_key = ApiKey(
        name=payload.name,
        key_hash=key_hash,
        prefix=raw_key[:8],
        creator_id=user["sub"]
    )
    
    db.add(api_key)
    await db.commit()
    
    resp = api_key.to_dict()
    resp["raw_key"] = raw_key
    return ApiKeyResponse(**resp)

@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: str,
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(ApiKey).where(ApiKey.id == key_id, ApiKey.creator_id == user["sub"]))
    api_key = result.scalars().first()
    
    if not api_key:
        raise HTTPException(status_code=404, detail="API Key not found")
        
    api_key.is_active = False
    await db.commit()
    return {"message": "API Key revoked"}
