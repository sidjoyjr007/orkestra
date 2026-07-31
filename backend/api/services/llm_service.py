import time
import httpx
from typing import List, Optional, Dict
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, cast, String, func
from backend.api.models.llm import LlmConfig

class LlmService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_llms(self, user_id: str, user_role: str) -> List[dict]:
        query = select(LlmConfig)
        
        if user_role != "ADMIN":
            query = query.where(
                or_(
                    LlmConfig.creator_id == user_id,
                    func.coalesce(LlmConfig.is_public, False) == True,
                    func.coalesce(cast(LlmConfig.allowed_roles, String), '[]').like(f'%"{user_role}"%')
                )
            )
            
        result = await self.db.execute(query)
        llms = result.scalars().all()
        
        responses = []
        for llm in llms:
            responses.append({
                "id": llm.id,
                "name": llm.name,
                "provider": llm.provider,
                "model_name": llm.model_name,
                "endpoint_url": llm.endpoint_url,
                "headers": llm.headers,
                "has_api_key": bool(llm.api_key_encrypted),
                "allowed_roles": llm.allowed_roles or [],
                "is_public": bool(llm.is_public),
                "creator_id": llm.creator_id
            })
        return responses

    async def create_llm(self, payload_dict: dict, creator_id: str) -> dict:
        new_llm = LlmConfig(
            name=payload_dict["name"],
            provider=payload_dict["provider"].upper(),
            model_name=payload_dict["model_name"],
            endpoint_url=payload_dict.get("endpoint_url"),
            headers=payload_dict.get("headers") or {},
            allowed_roles=payload_dict.get("allowed_roles") or [],
            is_public=payload_dict.get("is_public", False),
            creator_id=creator_id
        )
        if payload_dict.get("api_key"):
            new_llm.api_key = payload_dict["api_key"]
            
        self.db.add(new_llm)
        await self.db.commit()
        await self.db.refresh(new_llm)
        
        return {
            "id": new_llm.id,
            "name": new_llm.name,
            "provider": new_llm.provider,
            "model_name": new_llm.model_name,
            "endpoint_url": new_llm.endpoint_url,
            "headers": new_llm.headers,
            "has_api_key": bool(new_llm.api_key_encrypted),
            "allowed_roles": new_llm.allowed_roles or [],
            "is_public": bool(new_llm.is_public),
            "creator_id": new_llm.creator_id
        }

    async def update_llm(self, llm_id: str, payload_dict: dict, user_id: str, user_role: str) -> dict:
        result = await self.db.execute(select(LlmConfig).where(LlmConfig.id == llm_id))
        existing_llm = result.scalars().first()
        
        if not existing_llm:
            raise ValueError("LLM configuration not found")
            
        if user_role != "ADMIN" and existing_llm.creator_id != user_id:
            raise PermissionError("Not authorized to edit this LLM")
            
        existing_llm.name = payload_dict["name"]
        existing_llm.provider = payload_dict["provider"].upper()
        existing_llm.model_name = payload_dict["model_name"]
        existing_llm.endpoint_url = payload_dict.get("endpoint_url")
        existing_llm.headers = payload_dict.get("headers") or {}
        
        if payload_dict.get("api_key"):
            existing_llm.api_key = payload_dict["api_key"]
            
        if payload_dict.get("allowed_roles") is not None:
            existing_llm.allowed_roles = payload_dict["allowed_roles"]
                
        if payload_dict.get("is_public") is not None:
            existing_llm.is_public = payload_dict["is_public"]
            
        await self.db.commit()
        await self.db.refresh(existing_llm)
        
        return {
            "id": existing_llm.id,
            "name": existing_llm.name,
            "provider": existing_llm.provider,
            "model_name": existing_llm.model_name,
            "endpoint_url": existing_llm.endpoint_url,
            "headers": existing_llm.headers,
            "has_api_key": bool(existing_llm.api_key_encrypted),
            "allowed_roles": existing_llm.allowed_roles or [],
            "is_public": bool(existing_llm.is_public),
            "creator_id": existing_llm.creator_id
        }

    async def delete_llm(self, llm_id: str, user_id: str, user_role: str) -> None:
        result = await self.db.execute(select(LlmConfig).where(LlmConfig.id == llm_id))
        existing_llm = result.scalars().first()
        
        if not existing_llm:
            raise ValueError("LLM configuration not found")
            
        if user_role != "ADMIN" and existing_llm.creator_id != user_id:
            raise PermissionError("Only the creator or ADMIN can delete this LLM")
            
        await self.db.delete(existing_llm)
        await self.db.commit()

    async def test_llm(self, llm_id: str, prompt: str, user_id: str, user_role: str) -> dict:
        result = await self.db.execute(select(LlmConfig).where(LlmConfig.id == llm_id))
        llm = result.scalars().first()
        
        if not llm:
            raise ValueError("LLM configuration not found")
            
        if user_role != "ADMIN" and llm.creator_id != user_id:
            if user_role not in (llm.allowed_roles or []):
                raise PermissionError("Not authorized to access this LLM")
            
        api_key = llm.api_key
        provider = llm.provider
        model = llm.model_name
        
        start_time = time.time()
        
        async with httpx.AsyncClient(timeout=30.0) as client:
            if provider in ["OPENAI", "VLLM"]:
                url = llm.endpoint_url or "https://api.openai.com/v1/chat/completions"
                headers = {"Content-Type": "application/json"}
                if api_key:
                    headers["Authorization"] = f"Bearer {api_key}"
                if llm.headers:
                    headers.update(llm.headers)
                    
                data = {
                    "model": model,
                    "messages": [{"role": "user", "content": prompt}]
                }
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                res_json = response.json()
                content = res_json["choices"][0]["message"]["content"]
                
            elif provider == "ANTHROPIC":
                url = "https://api.anthropic.com/v1/messages"
                headers = {
                    "x-api-key": api_key or "",
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json"
                }
                data = {
                    "model": model,
                    "max_tokens": 1024,
                    "messages": [{"role": "user", "content": prompt}]
                }
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                res_json = response.json()
                content = res_json["content"][0]["text"]
                
            elif provider == "GEMINI":
                url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}"
                headers = {"Content-Type": "application/json"}
                data = {
                    "contents": [{"parts": [{"text": prompt}]}]
                }
                response = await client.post(url, headers=headers, json=data)
                response.raise_for_status()
                res_json = response.json()
                content = res_json["candidates"][0]["content"]["parts"][0]["text"]
                
            else:
                raise ValueError(f"Unsupported provider: {provider}")
                
        elapsed = round((time.time() - start_time) * 1000)
        
        return {
            "status": "success",
            "content": content,
            "elapsed_ms": elapsed
        }
