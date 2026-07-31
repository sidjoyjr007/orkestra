import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship
from backend.api.core.database import Base

class McpConfig(Base):
    __tablename__ = "mcps"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True, nullable=False)
    endpoint = Column(String, nullable=False)
    headers = Column(JSONB, default=dict)
    secrets = Column(JSONB, default=list) # e.g. [{"key": "MY_KEY", "value": "encrypted_value"}]
    is_public = Column(Boolean, default=False)
    allowed_roles = Column(JSONB, default=list)
    
    creator_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    creator = relationship("User")
