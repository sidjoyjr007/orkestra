from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token, require_permission
from backend.api.models.role import Role

router = APIRouter()

class RoleCreateUpdate(BaseModel):
    name: str
    permissions: List[str]

@router.get("")
async def get_roles(
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    """List all available roles. Any authenticated user can read roles."""
    result = await db.execute(select(Role))
    roles = result.scalars().all()
    return {"items": [{"id": r.id, "name": r.name, "permissions": r.permissions} for r in roles]}

@router.post("")
async def create_role(
    payload: RoleCreateUpdate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db)
):
    name = payload.name.upper()
    result = await db.execute(select(Role).where(Role.name == name))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Role already exists")
        
    new_role = Role(name=name, permissions=payload.permissions)
    db.add(new_role)
    await db.commit()
    return {"message": "Role created successfully"}

@router.put("/{role_id}")
async def update_role(
    role_id: str,
    payload: RoleCreateUpdate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    if role.name in ["ADMIN", "DEVELOPER", "VIEWER"]:
        # Prevent renaming core roles, but allow permission updates
        if payload.name.upper() != role.name:
            raise HTTPException(status_code=400, detail="Cannot rename core system roles")
            
    role.name = payload.name.upper()
    role.permissions = payload.permissions
    await db.commit()
    return {"message": "Role updated successfully"}

@router.delete("/{role_id}")
async def delete_role(
    role_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("roles:manage")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Role).where(Role.id == role_id))
    role = result.scalars().first()
    if not role:
        raise HTTPException(status_code=404, detail="Role not found")
        
    if role.name in ["ADMIN", "DEVELOPER", "VIEWER"]:
        raise HTTPException(status_code=400, detail="Cannot delete core system roles")
        
    await db.delete(role)
    await db.commit()
    return {"message": "Role deleted successfully"}
