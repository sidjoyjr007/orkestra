from sqlalchemy import Column, Integer, String, Text, DateTime, JSON
from datetime import datetime
from backend.api.core.database import Base

class MessageModel(Base):
    __tablename__ = 'orkestra_messages'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(255), index=True, nullable=False)
    role = Column(String(50), nullable=False)
    content = Column(Text, nullable=True)
    name = Column(String(255), nullable=True)
    tool_calls = Column(JSON, nullable=True)
    tool_call_id = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
