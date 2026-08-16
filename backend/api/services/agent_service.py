import uuid
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, cast, String, func
from backend.api.models.agent import AgentConfig
from backend.api.models.deployment import AgentDeployment
from backend.api.core.deployment.provider import LocalDockerProvider

class AgentService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_agents(
        self,
        user_id: str,
        role: str,
        limit: int = 50,
        offset: int = 0,
        q: Optional[str] = None
    ) -> dict:
        query = select(AgentConfig)
        
        if role != "ADMIN":
            query = query.where(
                or_(
                    AgentConfig.creator_id == user_id,
                    func.coalesce(AgentConfig.is_public, False) == True,
                    func.coalesce(cast(AgentConfig.allowed_roles, String), '[]').like(f'%"{role}"%')
                )
            )
            
        if q:
            query = query.where(AgentConfig.name.ilike(f"%{q}%"))
            
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        agents = result.scalars().all()
        
        formatted_agents = []
        for a in agents:
            formatted_agents.append({
                "id": str(a.id),
                "name": a.name,
                "description": a.description,
                "system_prompt": a.system_prompt,
                "llm": a.llm,
                "llmProvider": a.llmProvider,
                "selectedTools": a.selectedTools or [],
                "selectedMcps": a.selectedMcps or [],
                "selectedGuardrails": a.selectedGuardrails or [],
                "max_iterations": a.max_iterations or 20,
                "compaction_tokens": a.compaction_tokens or 30000,
                "allowed_roles": a.allowed_roles or [],
                "is_public": bool(a.is_public),
                "creator_id": str(a.creator_id)
            })
            
        return {"items": formatted_agents, "total": len(formatted_agents)}

    async def create_agent(self, payload_dict: dict, creator_id: str) -> str:
        agent_id = payload_dict.get("id") if payload_dict.get("id") else str(uuid.uuid4())
        
        new_agent = AgentConfig(
            id=agent_id,
            name=payload_dict["name"],
            description=payload_dict["description"],
            system_prompt=payload_dict["system_prompt"],
            llm=payload_dict["llm"],
            llmProvider=payload_dict["llmProvider"],
            selectedTools=payload_dict.get("selectedTools", []),
            selectedMcps=payload_dict.get("selectedMcps", []),
            selectedGuardrails=payload_dict.get("selectedGuardrails", []),
            max_iterations=payload_dict.get("max_iterations", 20),
            compaction_tokens=payload_dict.get("compaction_tokens", 30000),
            allowed_roles=payload_dict.get("allowed_roles") or [],
            is_public=payload_dict.get("is_public", False),
            creator_id=creator_id
        )
        self.db.add(new_agent)
        await self.db.commit()
        return agent_id

    async def update_agent(self, agent_id: str, payload_dict: dict, user_id: str, user_role: str) -> None:
        result = await self.db.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        agent = result.scalars().first()
        
        if not agent:
            raise ValueError("Agent not found")
            
        if agent.creator_id != user_id and user_role != "ADMIN":
            raise PermissionError("Not authorized to edit this agent")
            
        agent.name = payload_dict["name"]
        agent.description = payload_dict["description"]
        agent.system_prompt = payload_dict["system_prompt"]
        agent.llm = payload_dict["llm"]
        agent.llmProvider = payload_dict["llmProvider"]
        agent.selectedTools = payload_dict.get("selectedTools", [])
        agent.selectedMcps = payload_dict.get("selectedMcps", [])
        agent.selectedGuardrails = payload_dict.get("selectedGuardrails", [])
        
        if payload_dict.get("max_iterations") is not None:
            agent.max_iterations = payload_dict["max_iterations"]
        if payload_dict.get("compaction_tokens") is not None:
            agent.compaction_tokens = payload_dict["compaction_tokens"]
        if payload_dict.get("allowed_roles") is not None:
            agent.allowed_roles = payload_dict["allowed_roles"]
        if payload_dict.get("is_public") is not None:
            agent.is_public = payload_dict["is_public"]
        
        await self.db.commit()

    async def delete_agent(self, agent_id: str, user_id: str, user_role: str) -> None:
        result = await self.db.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        agent = result.scalars().first()
        
        if not agent:
            raise ValueError("Agent not found")
            
        if agent.creator_id != user_id and user_role != "ADMIN":
            raise PermissionError("Only the creator or ADMIN can delete this agent")
            
        # Get deployment to remove container and isolated volume
        dep_result = await self.db.execute(select(AgentDeployment).where(AgentDeployment.agent_id == agent_id))
        deployment = dep_result.scalars().first()
        if deployment and deployment.container_id:
            try:
                provider = LocalDockerProvider()
                await provider.remove(deployment.container_id)
                await provider.cleanup_volumes(f"orkestra-agent-{agent_id}")
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning(f"Failed to remove agent container/volume: {e}")
                
        await self.db.delete(agent)
        await self.db.commit()
