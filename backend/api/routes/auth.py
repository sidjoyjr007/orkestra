from fastapi import APIRouter, Depends, HTTPException, status, Response, Request
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from pydantic import BaseModel
from typing import Optional

from backend.api.core.database import get_db
from backend.api.models.user import User
from backend.api.models.role import Role
from backend.api.core.security import (
    get_password_hash, 
    verify_password, 
    create_access_token, 
    create_refresh_token,
    verify_token
)

router = APIRouter()

# --- Pydantic Schemas ---
class UserCreate(BaseModel):
    email: str
    password: str

class UserLogin(BaseModel):
    email: str
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    role: str
    is_active: bool

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

# --- Routes ---

@router.post("/signup", status_code=status.HTTP_201_CREATED)
async def signup(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if user exists
    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalars().first():
        raise HTTPException(status_code=400, detail="Email already registered")
        
    hashed_password = get_password_hash(user_data.password)
    
    # First user gets ADMIN and is instantly active. Others are VIEWER and inactive (pending).
    count_result = await db.execute(select(User))
    is_first = len(count_result.scalars().all()) == 0
    role = "ADMIN" if is_first else "VIEWER"
    is_active = True if is_first else False
    
    new_user = User(
        email=user_data.email, 
        hashed_password=hashed_password,
        role=role,
        is_active=is_active
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    
    if is_active:
        return {"message": "Admin account created successfully.", "is_active": True}
    else:
        return {"message": "Account created. Pending Administrator approval.", "is_active": False}


@router.post("/login")
async def login(response: Response, user_data: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == user_data.email))
    user = result.scalars().first()
    
    if not user or not verify_password(user_data.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid credentials")
        
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled or pending administrator approval.")
        
    # Fetch Role Permissions
    role_result = await db.execute(select(Role).where(Role.name == user.role))
    role_record = role_result.scalars().first()
    permissions = role_record.permissions if role_record else []
    
    # Generate Tokens
    access_token = create_access_token({"sub": user.id, "role": user.role, "permissions": permissions})
    refresh_token = create_refresh_token({"sub": user.id})
    
    # Set strictly secure HTTPOnly cookies
    response.set_cookie(
        key="access_token", 
        value=access_token, 
        httponly=True, 
        secure=False, # Set to True in production (HTTPS)
        samesite="lax", # Lax for localhost cross-port
        max_age=30 * 60 # 30 mins
    )
    response.set_cookie(
        key="refresh_token", 
        value=refresh_token, 
        httponly=True, 
        secure=False,
        samesite="lax",
        max_age=7 * 24 * 60 * 60 # 7 days
    )
    
    return {"message": "Login successful", "role": user.role}


@router.post("/logout")
async def logout(response: Response):
    # Clearing the HTTPOnly cookies instantly invalidates the session
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")
    return {"message": "Logged out successfully"}


@router.get("/me")
async def get_current_user(request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    payload = verify_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token")
        
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is disabled")
            
    # Fetch permissions
    role_result = await db.execute(select(Role).where(Role.name == user.role))
    role_record = role_result.scalars().first()
    permissions = role_record.permissions if role_record else []
    
    return {
        "id": user.id,
        "email": user.email,
        "role": user.role,
        "is_active": user.is_active,
        "permissions": permissions
    }


@router.post("/refresh")
async def refresh_token(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    refresh_t = request.cookies.get("refresh_token")
    if not refresh_t:
        raise HTTPException(status_code=401, detail="Missing refresh token")
        
    payload = verify_token(refresh_t)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid refresh token")
        
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalars().first()
    if not user or not user.is_active:
        raise HTTPException(status_code=403, detail="Invalid user or disabled account")
        
    # Fetch permissions
    role_result = await db.execute(select(Role).where(Role.name == user.role))
    role_record = role_result.scalars().first()
    permissions = role_record.permissions if role_record else []
    
    # Generate new access token
    new_access_token = create_access_token({"sub": user.id, "role": user.role, "permissions": permissions})
    response.set_cookie(
        key="access_token", 
        value=new_access_token, 
        httponly=True, 
        secure=False,
        samesite="lax",
        max_age=30 * 60
    )
    return {"message": "Token refreshed"}

@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, request: Request, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get("access_token")
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
        
    payload = verify_token(token)
    if not payload or not payload.get("sub"):
        raise HTTPException(status_code=401, detail="Invalid token")
        
    result = await db.execute(select(User).where(User.id == payload["sub"]))
    user = result.scalars().first()
    
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
        
    if not verify_password(req.current_password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect current password")
        
    user.hashed_password = get_password_hash(req.new_password)
    await db.commit()
    
    return {"message": "Password changed successfully"}
