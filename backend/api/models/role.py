import uuid
from sqlalchemy import Column, String
from sqlalchemy.dialects.postgresql import JSONB
from backend.api.core.database import Base

class Role(Base):
    __tablename__ = "roles"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, unique=True, index=True, nullable=False)
    permissions = Column(JSONB, default=list)
