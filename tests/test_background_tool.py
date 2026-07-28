import pytest
import asyncio
from unittest.mock import AsyncMock, patch

from orkestra.core.background_tool import BackgroundTool
from orkestra.events.bus import EventBus
from orkestra.events.base import TaskCompletedEvent
from orkestra.core.exceptions import WorkflowPausedError

@pytest.fixture
def event_bus():
    bus = EventBus()
    bus.apublish = AsyncMock()
    return bus

async def sample_coro(a: int, b: float, c: bool, d: str = "default"):
    await asyncio.sleep(0.01)
    return f"{a}-{b}-{c}-{d}"

async def error_coro():
    await asyncio.sleep(0.01)
    raise ValueError("Test error")

def test_background_tool_initialization(event_bus):
    tool = BackgroundTool("test_bg", "desc", sample_coro, event_bus)
    
    assert tool.name == "test_bg"
    assert tool.description == "desc"
    
    schema = tool.schema
    props = schema["function"]["parameters"]["properties"]
    
    assert props["a"]["type"] == "integer"
    assert props["b"]["type"] == "number"
    assert props["c"]["type"] == "boolean"
    assert props["d"]["type"] == "string"
    
    assert "a" in schema["function"]["parameters"]["required"]
    assert "b" in schema["function"]["parameters"]["required"]
    assert "c" in schema["function"]["parameters"]["required"]
    assert "d" not in schema["function"]["parameters"]["required"]

@pytest.mark.asyncio
async def test_background_tool_arun_success(event_bus):
    tool = BackgroundTool("test_bg", "desc", sample_coro, event_bus)
    
    # Tool raises immediately
    with pytest.raises(WorkflowPausedError) as exc_info:
        await tool.arun(
            _session_id="session1", 
            _tool_call_id="c1", 
            _agent_name="agent1",
            a=1, b=2.0, c=True, d="test"
        )
        
    assert "Sleeping" in str(exc_info.value)
    
    # Let the background task run
    await asyncio.sleep(0.05)
    
    event_bus.apublish.assert_awaited_once()
    event = event_bus.apublish.call_args[0][0]
    
    assert isinstance(event, TaskCompletedEvent)
    assert event.session_id == "session1"
    assert event.tool_call_id == "c1"
    assert event.agent_name == "agent1"
    assert event.result == "1-2.0-True-test"

@pytest.mark.asyncio
async def test_background_tool_arun_error(event_bus):
    tool = BackgroundTool("test_bg", "desc", error_coro, event_bus)
    
    # Tool raises immediately
    with pytest.raises(WorkflowPausedError):
        await tool.arun(
            _session_id="session1", 
            _tool_call_id="c1", 
            _agent_name="agent1"
        )
        
    # Let the background task run
    await asyncio.sleep(0.05)
    
    event_bus.apublish.assert_awaited_once()
    event = event_bus.apublish.call_args[0][0]
    
    assert isinstance(event, TaskCompletedEvent)
    assert event.result == "Error in background task: Test error"
