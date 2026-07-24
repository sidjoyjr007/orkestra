import pytest
import asyncio
from typing import List, Dict, Any, Optional
from orkestra.core.messages import Message, ToolCall, Response, ResponseChunk
from orkestra.providers.base import BaseProvider
from orkestra.memory.in_memory import InMemoryStore
from orkestra.events.bus import EventBus

class MockProvider(BaseProvider):
    def __init__(self, responses: List[Response]):
        super().__init__("mock")
        self.responses = responses
        self.call_count = 0
        self.last_messages = None

    def generate(self, messages, temperature=0.7, max_tokens=None, tools=None, **kwargs) -> Response:
        return Response(message=Message(role="assistant", content="Mock"))

    def generate_stream(self, messages, temperature=0.7, max_tokens=None, tools=None, **kwargs):
        yield ResponseChunk(delta="Mock")

    async def agenerate_stream(self, messages, temperature=0.7, max_tokens=None, tools=None, **kwargs):
        yield ResponseChunk(delta="Mock")

    async def agenerate(
        self,
        messages: List[Message],
        system_prompt: Optional[str] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Response:
        self.last_messages = messages
        
        if self.call_count >= len(self.responses):
            return Response(message=Message(role="assistant", content="Default mock response"))
            
        resp = self.responses[self.call_count]
        self.call_count += 1
        return resp

@pytest.fixture
def event_bus():
    return EventBus()

@pytest.fixture
def memory_store():
    return InMemoryStore()
