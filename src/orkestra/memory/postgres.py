import json
from datetime import datetime
from typing import List, Optional
import asyncio

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.future import select

from orkestra.core.messages import Message, ToolCall
from orkestra.memory.base import BaseMemory

Base = declarative_base()

class MessageModel(Base):
    __tablename__ = 'orkestra_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), index=True, nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)
    name = Column(String(255), nullable=True)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class AgentStateModel(Base):
    __tablename__ = 'orkestra_agent_states'
    
    session_id = Column(String(255), primary_key=True)
    state = Column(JSON, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class PostgresMemoryStore(BaseMemory):
    """
    Persistent memory store using PostgreSQL via SQLAlchemy.
    Supports both synchronous and asynchronous operations.
    """
    def __init__(self, db_url: str):
        # Convert base postgresql:// URL to specific drivers if needed
        if db_url.startswith("postgresql://"):
            sync_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
            async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        elif db_url.startswith("sqlite://"):
            sync_url = db_url
            async_url = db_url.replace("sqlite://", "sqlite+aiosqlite://")
        else:
            sync_url = db_url
            async_url = db_url
        
        # Sync engine
        self.engine = create_engine(sync_url, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Async engine
        self.async_engine = create_async_engine(async_url, pool_pre_ping=True)
        self.AsyncSessionLocal = async_sessionmaker(bind=self.async_engine, class_=AsyncSession)
        
        # Automatically create schema
        Base.metadata.create_all(bind=self.engine)

    def _message_to_model(self, session_id: str, message: Message) -> MessageModel:
        tool_calls_data = None
        if message.tool_calls:
            tool_calls_data = [
                {
                    "id": tc.id,
                    "function_name": tc.function_name,
                    "function_arguments": tc.function_arguments
                }
                for tc in message.tool_calls
            ]
            
        return MessageModel(
            session_id=session_id,
            role=message.role,
            content=message.content,
            name=message.name,
            tool_calls=tool_calls_data,
            tool_call_id=message.tool_call_id
        )

    def _model_to_message(self, model: MessageModel) -> Message:
        tool_calls = None
        if model.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc["id"],
                    function_name=tc["function_name"],
                    function_arguments=tc["function_arguments"]
                )
                for tc in model.tool_calls
            ]
            
        return Message(
            role=model.role,
            content=model.content,
            name=model.name,
            tool_calls=tool_calls,
            tool_call_id=model.tool_call_id
        )

    def add_message(self, session_id: str, message: Message) -> None:
        with self.SessionLocal() as session:
            model = self._message_to_model(session_id, message)
            session.add(model)
            session.commit()

    def get_messages(self, session_id: str) -> List[Message]:
        with self.SessionLocal() as session:
            models = session.query(MessageModel).filter(MessageModel.session_id == session_id).order_by(MessageModel.id).all()
            return [self._model_to_message(m) for m in models]

    def clear(self, session_id: str) -> None:
        with self.SessionLocal() as session:
            session.query(MessageModel).filter(MessageModel.session_id == session_id).delete()
            session.commit()

    async def aadd_message(self, session_id: str, message: Message) -> None:
        async with self.AsyncSessionLocal() as session:
            model = self._message_to_model(session_id, message)
            session.add(model)
            await session.commit()

    async def aget_messages(self, session_id: str) -> List[Message]:
        async with self.AsyncSessionLocal() as session:
            stmt = select(MessageModel).where(MessageModel.session_id == session_id).order_by(MessageModel.id)
            result = await session.execute(stmt)
            models = result.scalars().all()
            return [self._model_to_message(m) for m in models]

    async def aclear(self, session_id: str) -> None:
        async with self.AsyncSessionLocal() as session:
            from sqlalchemy import delete
            stmt = delete(MessageModel).where(MessageModel.session_id == session_id)
            await session.execute(stmt)
            await session.commit()

    async def asave_checkpoint(self, session_id: str, state: dict) -> None:
        async with self.AsyncSessionLocal() as session:
            # Upsert the state using merge
            model = AgentStateModel(session_id=session_id, state=state)
            await session.merge(model)
            await session.commit()
            
    async def aload_checkpoint(self, session_id: str) -> dict:
        async with self.AsyncSessionLocal() as session:
            stmt = select(AgentStateModel).where(AgentStateModel.session_id == session_id)
            result = await session.execute(stmt)
            model = result.scalar_one_or_none()
            if model:
                return model.state
            return {}

    async def aclear_checkpoint(self, session_id: str) -> None:
        async with self.AsyncSessionLocal() as session:
            from sqlalchemy import delete
            stmt = delete(AgentStateModel).where(AgentStateModel.session_id == session_id)
            await session.execute(stmt)
            await session.commit()
