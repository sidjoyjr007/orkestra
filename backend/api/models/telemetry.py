from sqlalchemy import Column, String, Integer, DateTime, JSON, Float
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from backend.api.core.database import Base

class AgentRun(Base):
    __tablename__ = "agent_runs"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(String, index=True, nullable=False)
    session_id = Column(String, index=True, nullable=False)
    status = Column(String, default="IN_PROGRESS") # IN_PROGRESS, COMPLETED, FAILED
    start_time = Column(DateTime, default=datetime.utcnow)
    end_time = Column(DateTime, nullable=True)
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

class RunEvent(Base):
    __tablename__ = "run_events"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    run_id = Column(UUID(as_uuid=True), index=True, nullable=False) # References AgentRun
    event_type = Column(String, nullable=False) # e.g. ToolExecutionStarted, GuardrailTriggered
    timestamp = Column(DateTime, default=datetime.utcnow)
    details = Column(JSON, nullable=True) # Payload details like tool_name, guardrail_message, etc.
