from sqlalchemy import Column, String, Boolean, ForeignKey
from sqlalchemy.dialects.postgresql import UUID, JSONB
import uuid
from backend.api.core.database import Base

class GuardrailConfig(Base):
    __tablename__ = "guardrails"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String, unique=True, index=True)
    description = Column(String)
    stage = Column(String, default="input") # input, output, action
    action = Column(String, default="block") # block, redact, feedback
    handlerType = Column(String, default="regex") # regex, llm-as-judge (Notice: handlerType instead of handler_type for frontend compatibility)
    rules = Column(String) # regex pattern or LLM prompt
    allowed_roles = Column(JSONB, default=list)
    is_public = Column(Boolean, default=False)
    creator_id = Column(String, ForeignKey("users.id"), nullable=True)
