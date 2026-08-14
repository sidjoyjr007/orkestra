from sqlalchemy import Column, String, ForeignKey, DateTime, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
import uuid
from datetime import datetime
from backend.api.core.database import Base

class Swarm(Base):
    __tablename__ = "swarms"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, nullable=False)
    description = Column(String)
    leader_agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    leader = relationship("AgentConfig", foreign_keys=[leader_agent_id])
    subagents = relationship("SwarmAgent", back_populates="swarm", cascade="all, delete-orphan")

class SwarmAgent(Base):
    """Mapping table that links a Swarm to its authorized Subagents."""
    __tablename__ = "swarm_agents"
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    swarm_id = Column(UUID(as_uuid=True), ForeignKey("swarms.id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False)
    role_description = Column(Text, nullable=True) # Optional specific instructions for this subagent within this swarm

    swarm = relationship("Swarm", back_populates="subagents")
    agent = relationship("AgentConfig", foreign_keys=[agent_id])
