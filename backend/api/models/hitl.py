import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON
from backend.api.core.database import Base

class HitlSession(Base):
    __tablename__ = "hitl_sessions"

    id = Column(String, primary_key=True, default=lambda: uuid.uuid4().hex)
    agent_id = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False, index=True)
    
    # "PENDING", "APPROVED", "REJECTED", "RESPONDED"
    status = Column(String, nullable=False, default="PENDING")
    
    # "TOOL_APPROVAL" or "USER_INPUT"
    request_type = Column(String, nullable=False)
    
    # Context stores the tool name, arguments, or the user input request message
    context = Column(JSON, nullable=False, default=dict)
    
    # External webhook url for when it's resolved
    webhook_url = Column(String, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)
    
    def to_dict(self):
        return {
            "id": self.id,
            "agent_id": self.agent_id,
            "session_id": self.session_id,
            "status": self.status,
            "request_type": self.request_type,
            "context": self.context,
            "webhook_url": self.webhook_url,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None
        }
