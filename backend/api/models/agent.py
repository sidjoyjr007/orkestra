import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey, Integer
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.api.core.database import Base
from backend.api.models.user import User

class AgentConfig(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    system_prompt = Column(Text, nullable=True)
    llm = Column(String, nullable=False)
    llmProvider = Column(String, nullable=False)
    
    selectedTools = Column(JSONB, default=list)
    selectedMcps = Column(JSONB, default=list)
    selectedGuardrails = Column(JSONB, default=list)
    
    max_iterations = Column(Integer, default=20)
    compaction_tokens = Column(Integer, default=30000)
    
    allowed_roles = Column(JSONB, default=list)
    is_public = Column(Boolean, default=False)
    
    creator_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationship to user
    creator = relationship("User", backref="agents")
