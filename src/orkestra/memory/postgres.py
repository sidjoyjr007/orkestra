import json
from datetime import datetime
from typing import List, Optional, Any
import asyncio

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import create_engine
from sqlalchemy.future import select

from orkestra.core.messages import Message, ToolCall
from orkestra.memory.base import BaseMemory
from orkestra.events.base import MemoryReadEvent, MemoryWrittenEvent

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
    def __init__(self, db_url: str, event_bus: Optional[Any] = None):
        super().__init__(event_bus)
        # Convert base postgresql:// URL to specific drivers if needed
        if db_url.startswith("postgresql://"):
            sync_url = db_url.replace("postgresql://", "postgresql+psycopg2://")
            async_url = db_url.replace("postgresql://", "postgresql+asyncpg://")
        elif db_url.startswith("postgresql+asyncpg://"):
            sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
            async_url = db_url
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

    def _model_to_message(self, model: MessageModel) -> Message:
        tool_calls = None
        if model.tool_calls:
            tool_calls = []
            for tc_dict in model.tool_calls:
                tc = ToolCall(
                    id=tc_dict.get("id"),
                    type=tc_dict.get("type", "function"),
                    function_name=tc_dict.get("function_name") or tc_dict.get("function", {}).get("name"),
                    function_arguments=tc_dict.get("function_arguments") or tc_dict.get("function", {}).get("arguments")
                )
                tool_calls.append(tc)

        return Message(
            role=model.role,
            content=model.content,
            name=model.name,
            tool_calls=tool_calls,
            tool_call_id=model.tool_call_id
        )

    def _message_to_model(self, session_id: str, model: Message) -> MessageModel:
        tool_calls = None
        if model.tool_calls:
            tool_calls = [
                {
                    "id": tc.id,
                    "type": tc.type,
                    "function_name": tc.function_name,
                    "function_arguments": tc.function_arguments
                } for tc in model.tool_calls
            ]
            
        return MessageModel(
            session_id=session_id,
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
            if self.event_bus:
                self.event_bus.publish(MemoryWrittenEvent(session_id=session_id, role=message.role))

    def get_messages(self, session_id: str) -> List[Message]:
        with self.SessionLocal() as session:
            models = session.query(MessageModel).filter(MessageModel.session_id == session_id).order_by(MessageModel.id).all()
            messages = [self._model_to_message(m) for m in models]
            if self.event_bus:
                self.event_bus.publish(MemoryReadEvent(session_id=session_id, message_count=len(messages)))
            return messages

    def clear(self, session_id: str) -> None:
        with self.SessionLocal() as session:
            session.query(MessageModel).filter(MessageModel.session_id == session_id).delete()
            session.commit()

    async def aadd_message(self, session_id: str, message: Message) -> None:
        async with self.AsyncSessionLocal() as session:
            model = self._message_to_model(session_id, message)
            session.add(model)
            await session.commit()
            if self.event_bus:
                self.event_bus.publish(MemoryWrittenEvent(session_id=session_id, role=message.role))

    async def aget_messages(self, session_id: str) -> List[Message]:
        async with self.AsyncSessionLocal() as session:
            stmt = select(MessageModel).where(MessageModel.session_id == session_id).order_by(MessageModel.id)
            result = await session.execute(stmt)
            models = result.scalars().all()
            messages = [self._model_to_message(m) for m in models]
            if self.event_bus:
                self.event_bus.publish(MemoryReadEvent(session_id=session_id, message_count=len(messages)))
            return messages

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
