import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, cast, String, func
from backend.api.models.guardrail import GuardrailConfig

class GuardrailService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_guardrails(
        self,
        user_id: str,
        user_role: str,
        limit: int = 50,
        offset: int = 0,
        q: Optional[str] = None
    ) -> dict:
        query = select(GuardrailConfig)
        
        if user_role != "ADMIN":
            query = query.where(
                or_(
                    GuardrailConfig.creator_id == user_id,
                    func.coalesce(GuardrailConfig.is_public, False) == True,
                    func.coalesce(cast(GuardrailConfig.allowed_roles, String), '[]').like(f'%"{user_role}"%')
                )
            )
        
        if q:
            query = query.where(GuardrailConfig.name.ilike(f"%{q}%"))
            
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        guardrails = result.scalars().all()
        
        formatted = []
        for g in guardrails:
            formatted.append({
                "id": str(g.id),
                "name": g.name,
                "description": g.description,
                "stage": g.stage,
                "action": g.action,
                "handlerType": g.handlerType,
                "rules": g.rules,
                "allowed_roles": g.allowed_roles or [],
                "is_public": bool(g.is_public),
                "creator_id": str(g.creator_id) if g.creator_id else None
            })
            
        return {"items": formatted, "total": len(formatted)}

    async def create_guardrail(self, payload_dict: dict, creator_id: str) -> str:
        new_id = payload_dict.get("id") if payload_dict.get("id") else str(uuid.uuid4())
        
        result = await self.db.execute(select(GuardrailConfig).where(GuardrailConfig.name == payload_dict["name"]))
        if result.scalars().first():
            raise ValueError("Guardrail with this name already exists")
            
        new_guardrail = GuardrailConfig(
            id=new_id,
            name=payload_dict["name"],
            description=payload_dict["description"],
            stage=payload_dict["stage"],
            action=payload_dict["action"],
            handlerType=payload_dict["handlerType"],
            rules=payload_dict["rules"],
            allowed_roles=payload_dict.get("allowed_roles") or [],
            is_public=payload_dict.get("is_public", False),
            creator_id=creator_id
        )
        self.db.add(new_guardrail)
        await self.db.commit()
        return new_id

    async def get_guardrail(self, guardrail_id: str, user_id: str, user_role: str) -> dict:
        result = await self.db.execute(select(GuardrailConfig).where(GuardrailConfig.id == guardrail_id))
        g = result.scalars().first()
        
        if not g:
            raise ValueError("Guardrail not found")
            
        if user_role != "ADMIN" and g.creator_id != user_id and not g.is_public and (g.allowed_roles and user_role not in g.allowed_roles):
            raise PermissionError("Not authorized to access this guardrail")
            
        return {
            "id": str(g.id),
            "name": g.name,
            "description": g.description,
            "stage": g.stage,
            "action": g.action,
            "handlerType": g.handlerType,
            "rules": g.rules,
            "allowed_roles": g.allowed_roles or [],
            "is_public": bool(g.is_public),
            "creator_id": str(g.creator_id) if g.creator_id else None
        }

    async def update_guardrail(self, guardrail_id: str, payload_dict: dict, user_id: str, user_role: str) -> None:
        result = await self.db.execute(select(GuardrailConfig).where(GuardrailConfig.id == guardrail_id))
        g = result.scalars().first()
        
        if not g:
            raise ValueError("Guardrail not found")
            
        if g.name != payload_dict["name"]:
            name_check = await self.db.execute(select(GuardrailConfig).where(GuardrailConfig.name == payload_dict["name"]))
            if name_check.scalars().first():
                raise ValueError("Guardrail with this name already exists")
                
        g.name = payload_dict["name"]
        g.description = payload_dict["description"]
        g.stage = payload_dict["stage"]
        g.action = payload_dict["action"]
        g.handlerType = payload_dict["handlerType"]
        g.rules = payload_dict["rules"]
        
        if payload_dict.get("allowed_roles") is not None:
            if user_role == "ADMIN" or g.creator_id == user_id:
                g.allowed_roles = payload_dict["allowed_roles"]
                
        if payload_dict.get("is_public") is not None:
            if user_role == "ADMIN" or g.creator_id == user_id:
                g.is_public = payload_dict["is_public"]
        
        await self.db.commit()

    async def delete_guardrail(self, guardrail_id: str) -> None:
        result = await self.db.execute(select(GuardrailConfig).where(GuardrailConfig.id == guardrail_id))
        g = result.scalars().first()
        
        if not g:
            raise ValueError("Guardrail not found")
            
        await self.db.delete(g)
        await self.db.commit()
