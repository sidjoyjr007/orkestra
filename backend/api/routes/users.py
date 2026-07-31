from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import List

from backend.api.core.database import get_db
from backend.api.models.user import User
from backend.api.core.dependencies import require_role

router = APIRouter()

class UserAdminResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool
    created_at: str

class RoleUpdateRequest(BaseModel):
    role: str

@router.get("/", response_model=List[UserAdminResponse])
async def list_users(
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["ADMIN"]))
):
    result = await db.execute(select(User).order_by(User.created_at.desc()))
    users = result.scalars().all()
    return [
        UserAdminResponse(
            id=u.id, 
            email=u.email, 
            role=u.role, 
            is_active=u.is_active,
            created_at=str(u.created_at)
        ) for u in users
    ]

@router.post("/{user_id}/approve")
async def approve_user(
    user_id: str, 
    req: RoleUpdateRequest,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["ADMIN"]))
):
    if req.role not in ["ADMIN", "DEVELOPER", "VIEWER"]:
        raise HTTPException(status_code=400, detail="Invalid role")
        
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    user.is_active = True
    user.role = req.role
    await db.commit()
    return {"message": "User approved successfully"}

@router.post("/{user_id}/revoke")
async def revoke_user(
    user_id: str,
    db: AsyncSession = Depends(get_db),
    _=Depends(require_role(["ADMIN"]))
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if user.role == "ADMIN":
        # Ensure we don't accidentally revoke the only admin
        count_result = await db.execute(select(User).where(User.role == "ADMIN", User.is_active == True))
        admins = count_result.scalars().all()
        if len(admins) <= 1:
            raise HTTPException(status_code=400, detail="Cannot revoke the last active administrator")
            
    user.is_active = False
    await db.commit()
    return {"message": "User access revoked"}
