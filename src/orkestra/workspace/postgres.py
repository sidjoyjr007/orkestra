import json
from typing import Optional
from sqlalchemy import Column, Integer, String, JSON
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.future import select

from orkestra.workspace.base import BaseWorkspaceStore, Plan

Base = declarative_base()

class PlanModel(Base):
    __tablename__ = 'orkestra_plans'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), index=True, nullable=False)
    status = Column(String(50), nullable=False)
    plan_data = Column(JSON, nullable=False)

class PostgresWorkspaceStore(BaseWorkspaceStore):
    def __init__(self, db_url: str):
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
            
            if not model:
                return None
                
            return Plan(**model.plan_data)
            
    async def asave_plan(self, plan: Plan) -> None:
        async with self.async_session() as session:
            # If creating a new active plan, archive any existing ones first
            if plan.status == "ACTIVE":
                stmt = select(PlanModel).where(
                    PlanModel.session_id == plan.session_id,
                    PlanModel.status == "ACTIVE"
                )
                result = await session.execute(stmt)
                existing_active = result.scalars().all()
                for e in existing_active:
                    e.status = "ARCHIVED"
            
            # Since we don't track plan IDs inherently in the Plan object easily,
            # we just insert a new state record or we could update if we tracked ID.
            # To keep history, we can just insert the new state. 
            # Or better, we can just keep one row per plan. 
            # Let's just insert the new snapshot.
            new_model = PlanModel(
                session_id=plan.session_id,
                status=plan.status,
                plan_data=plan.model_dump()
            )
            session.add(new_model)
            await session.commit()
            
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
