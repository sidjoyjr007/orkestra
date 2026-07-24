import asyncio
from typing import Dict, Optional
from orkestra.workspace.base import BaseWorkspaceStore, Plan

class InMemoryWorkspaceStore(BaseWorkspaceStore):
    def __init__(self):
        # Maps session_id -> list of Plans
        self.plans: Dict[str, list[Plan]] = {}
        
    async def aget_active_plan(self, session_id: str) -> Optional[Plan]:
        if session_id not in self.plans:
            return None
        
        for p in self.plans[session_id]:
            if p.status == "ACTIVE":
                return p
        return None
        
    async def asave_plan(self, plan: Plan) -> None:
        if plan.session_id not in self.plans:
            self.plans[plan.session_id] = []
            
        # If it's an existing plan (object identity or same active), replace it
        # Actually in memory we can just append, but we want to ensure only one active
        if plan.status == "ACTIVE":
            # ensure no other active plan exists
            for p in self.plans[plan.session_id]:
                if p != plan and p.status == "ACTIVE":
                    p.status = "ARCHIVED"
                    
        if plan not in self.plans[plan.session_id]:
            self.plans[plan.session_id].append(plan)
            
    async def aarchive_active_plan(self, session_id: str) -> None:
        active = await self.aget_active_plan(session_id)
        if active:
            active.status = "ARCHIVED"
