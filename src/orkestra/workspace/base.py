import abc
from typing import List, Optional
from pydantic import BaseModel, Field

class Task(BaseModel):
    id: int
    description: str
    status: str = Field(default="TODO", description="One of: TODO, IN_PROGRESS, DONE, BLOCKED")
    notes: Optional[str] = None

class Plan(BaseModel):
    session_id: str
    status: str = Field(default="ACTIVE", description="One of: ACTIVE, ARCHIVED")
    tasks: List[Task] = Field(default_factory=list)
    
    def to_markdown(self) -> str:
        if not self.tasks:
            return "No tasks in active plan."
            
        md = []
        for t in self.tasks:
            checkbox = "x" if t.status == "DONE" else " "
            note = f" (Notes: {t.notes})" if t.notes else ""
            status_tag = f" [{t.status}]" if t.status not in ("TODO", "DONE") else ""
            md.append(f"- [{checkbox}] {t.id}. {t.description}{status_tag}{note}")
            
        return "\n".join(md)

class BaseWorkspaceStore(abc.ABC):
    @abc.abstractmethod
    async def aget_active_plan(self, session_id: str) -> Optional[Plan]:
        """Fetch the currently active plan for the session."""
        pass
        
    @abc.abstractmethod
    async def asave_plan(self, plan: Plan) -> None:
        """Save a new plan or update an existing one."""
        pass
        
    @abc.abstractmethod
    async def aarchive_active_plan(self, session_id: str) -> None:
        """Archive the current active plan."""
        pass
