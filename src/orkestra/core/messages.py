from typing import Any, Dict, List, Literal, Optional, Union
from pydantic import BaseModel, Field

Role = Literal["system", "user", "assistant", "tool"]

class ToolCall(BaseModel):
    """Represents a tool call requested by the model."""
    id: str
    type: Literal["function"] = "function"
    function_name: str
    function_arguments: str  # usually JSON string

class Message(BaseModel):
    """Base generic message structure."""
    role: Role
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary."""
        return self.model_dump(exclude_none=True)

class ResponseChunk(BaseModel):
    """Represents a chunk of a streaming response."""
    content: Optional[str] = None
    tool_calls: Optional[List[ToolCall]] = None
    finish_reason: Optional[str] = None

class Response(BaseModel):
    """Represents a complete non-streaming response."""
    message: Message
    finish_reason: Optional[str] = None
    usage: Dict[str, int] = Field(default_factory=dict)
