import pytest
from unittest.mock import MagicMock, AsyncMock
from orkestra.workflows.background import WakeupService
from orkestra.events.bus import EventBus
from orkestra.events.base import TaskCompletedEvent

@pytest.mark.asyncio
async def test_wakeup_service_handle_task():
    bus = EventBus()
    registry = MagicMock()
    orchestrator = MagicMock()
    orchestrator.arun = AsyncMock()
    
    agent = MagicMock()
    agent.session_id = "old_session"
    agent.aadd_message = AsyncMock()
    registry.get_agent.return_value = agent
    
    service = WakeupService(bus, registry, orchestrator)
    
    event = TaskCompletedEvent(
        agent_name="test_agent",
        session_id="new_session",
        tool_call_id="call_123",
        result="some output"
    )
    
    await service._handle_task_completed(event)
    
    # Verify agent was looked up
    registry.get_agent.assert_called_once_with("test_agent")
    
    # Verify message was added
    agent.aadd_message.assert_called_once()
    msg = agent.aadd_message.call_args[0][0]
    assert msg.role == "tool"
    assert msg.content == "some output"
    assert msg.tool_call_id == "call_123"
    
    # Verify orchestrator was told to run
    orchestrator.arun.assert_called_once_with(
        entry_agent_name="test_agent",
        session_id="new_session",
        max_turns=5
    )

@pytest.mark.asyncio
async def test_wakeup_service_agent_not_found():
    bus = EventBus()
    registry = MagicMock()
    orchestrator = MagicMock()
    
    registry.get_agent.return_value = None
    
    service = WakeupService(bus, registry, orchestrator)
    
    event = TaskCompletedEvent(
        agent_name="unknown_agent",
        session_id="new_session",
        tool_call_id="call_123",
        result="some output"
    )
    
    await service._handle_task_completed(event)
    
    # Orchestrator should not run
    orchestrator.arun.assert_not_called()
