import json
from typing import Optional, Any
from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select

from orkestra.workspace.base import BaseWorkspaceStore, Plan
from orkestra.events.base import WorkspaceReadEvent, WorkspaceWrittenEvent

Base = declarative_base()

class PlanModel(Base):
    __tablename__ = 'orkestra_plans'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), index=True, nullable=False)
    status = Column(String(50), nullable=False)
    plan_data = Column(JSON, nullable=False)

class PostgresWorkspaceStore(BaseWorkspaceStore):
    def __init__(self, db_url: str, event_bus: Optional[Any] = None):
        super().__init__(event_bus)
        if db_url.startswith("postgres://"):
            db_url = db_url.replace("postgres://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("postgresql://"):
            db_url = db_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif db_url.startswith("sqlite"):
            if "aiosqlite" not in db_url:
                db_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
                
        self.engine = create_async_engine(db_url, echo=False)
        self.async_session = async_sessionmaker(
            self.engine, expire_on_commit=False, class_=AsyncSession
        )
        
    async def initialize(self):
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            
    async def aget_active_plan(self, session_id: str) -> Optional[Plan]:
        async with self.async_session() as session:
            stmt = select(PlanModel).where(
                PlanModel.session_id == session_id,
                PlanModel.status == "ACTIVE"
            ).order_by(PlanModel.id.desc())
            
            result = await session.execute(stmt)
            model = result.scalars().first()
            
            if self.event_bus:
                self.event_bus.publish(WorkspaceReadEvent(session_id=session_id, items_retrieved=1 if model else 0))
            
            if not model:
                return None
                
            return Plan(**model.plan_data)
            
    async def asave_plan(self, plan: Plan) -> None:
        async with self.async_session() as session:
            # Archive any existing active plan snapshots
            stmt = select(PlanModel).where(
                PlanModel.session_id == plan.session_id,
                PlanModel.status == "ACTIVE"
            )
            result = await session.execute(stmt)
            existing_active = result.scalars().all()
            for e in existing_active:
                e.status = "ARCHIVED"
            
            new_model = PlanModel(
                session_id=plan.session_id,
                status=plan.status,
                plan_data=plan.model_dump()
            )
            session.add(new_model)
            await session.commit()
            
            if self.event_bus:
                self.event_bus.publish(WorkspaceWrittenEvent(session_id=plan.session_id, action="save_plan"))
            
    async def aarchive_active_plan(self, session_id: str) -> None:
        async with self.async_session() as session:
            stmt = select(PlanModel).where(
                PlanModel.session_id == session_id,
                PlanModel.status == "ACTIVE"
            )
            result = await session.execute(stmt)
            existing_active = result.scalars().all()
            for e in existing_active:
                e.status = "ARCHIVED"
            
            await session.commit()
            
            if self.event_bus:
                self.event_bus.publish(WorkspaceWrittenEvent(session_id=session_id, action="archive_plan"))
