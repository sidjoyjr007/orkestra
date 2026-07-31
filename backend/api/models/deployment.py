from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID
import uuid
from datetime import datetime
from backend.api.core.database import Base

class AgentDeployment(Base):
    __tablename__ = "agent_deployments"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    agent_id = Column(UUID(as_uuid=True), index=True, nullable=False) # References AgentConfig
    container_id = Column(String, nullable=True) # ID from the orchestration provider
    port = Column(Integer, nullable=True)
    status = Column(String, default="STOPPED") # BUILDING, RUNNING, STOPPED, FAILED
    deployment_token = Column(String, nullable=True) # Secure token for HTTP config fetching
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
