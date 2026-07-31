from sqlalchemy import Column, String, Boolean, JSON, ForeignKey
from sqlalchemy.orm import relationship
import uuid
from backend.api.core.database import Base
from backend.api.core.crypto import encrypt_secret, decrypt_secret

class LlmConfig(Base):
    __tablename__ = "llms"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, index=True, nullable=False)
    provider = Column(String, nullable=False) # OPENAI, ANTHROPIC, GEMINI, CUSTOM
    model_name = Column(String, nullable=False)
    
    # Custom provider fields
    endpoint_url = Column(String, nullable=True)
    headers = Column(JSON, nullable=True, default=dict)
    
    # Encrypted API Key/Secret
    api_key_encrypted = Column(String, nullable=True)
    
    allowed_roles = Column(JSON, default=list)
    is_public = Column(Boolean, default=False)
    
    creator_id = Column(String, ForeignKey("users.id"), nullable=False)

    # Relationships
    creator = relationship("User")

    @property
    def api_key(self) -> str | None:
        if self.api_key_encrypted:
            return decrypt_secret(self.api_key_encrypted)
        return None

    @api_key.setter
    def api_key(self, raw_secret: str):
        if raw_secret:
            self.api_key_encrypted = encrypt_secret(raw_secret)
        else:
            self.api_key_encrypted = None
