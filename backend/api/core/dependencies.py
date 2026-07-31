from fastapi import Depends, HTTPException, Request
from backend.api.core.security import verify_token

from backend.api.core.database import AsyncSessionLocal
from sqlalchemy.future import select
from backend.api.models.api_key import ApiKey
import hashlib

async def get_current_user_token(request: Request) -> dict:
    auth_header = request.headers.get("Authorization")
    
    # 1. Check for Bearer API Key
    if auth_header and auth_header.startswith("Bearer "):
        api_key = auth_header.split(" ")[1]
        key_hash = hashlib.sha256(api_key.encode()).hexdigest()
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ApiKey).where(ApiKey.key_hash == key_hash, ApiKey.is_active == True))
            api_key_record = result.scalars().first()
            if api_key_record:
                # Mock a payload for API Key access
                # External programmatic access generally assumes full permissions, or we could add roles to ApiKey later
                return {
                    "sub": api_key_record.creator_id or "api-user",
                    "role": "ADMIN", 
                    "permissions": ["*"],
                    "is_api_key": True
                }
            raise HTTPException(status_code=401, detail="Invalid or revoked API Key")
            
    # 2. Check for Session Cookie
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    payload = verify_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token")
    return payload

def require_role(allowed_roles: list[str]):
    def role_checker(payload: dict = Depends(get_current_user_token)):
        user_role = payload.get("role")
        if not user_role or user_role not in allowed_roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return payload
    return role_checker

from backend.api.core.database import AsyncSessionLocal
from sqlalchemy.future import select
from backend.api.models.role import Role

def require_permission(permission: str):
    async def permission_checker(payload: dict = Depends(get_current_user_token)):
        permissions = payload.get("permissions")
        
        # Fallback for legacy tokens issued before the permissions array was embedded
        if permissions is None:
            user_role = payload.get("role")
            async with AsyncSessionLocal() as db:
                role_res = await db.execute(select(Role).where(Role.name == user_role))
                role_record = role_res.scalars().first()
                permissions = role_record.permissions if role_record else []
                
        if "*" in permissions or permission in permissions:
            return payload
        raise HTTPException(status_code=403, detail=f"Missing required permission: {permission}")
    return permission_checker
