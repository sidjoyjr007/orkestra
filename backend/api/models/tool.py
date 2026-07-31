import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, Boolean, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship
from backend.api.core.database import Base
from backend.api.models.user import User

class Tool(Base):
    __tablename__ = "tools"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True, nullable=False)
    description = Column(String, nullable=True)
    parameters = Column(JSONB, default=list)
    script = Column(Text, nullable=False)
    secrets = Column(JSONB, default=list)
    tool_type = Column(String, default="SANDBOX")
    is_public = Column(Boolean, default=False)
    status = Column(String, default="DRAFT")
    dependencies = Column(JSONB, default=list)
    entry_point = Column(String, default="execute")
    requires_approval = Column(Boolean, default=False)
    allowed_roles = Column(JSONB, default=list)
    
    creator_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # Relationship to user
    creator = relationship("User", backref="tools")
