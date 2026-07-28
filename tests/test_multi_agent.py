import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.multi_agent.orchestrator import Orchestrator
from orkestra.multi_agent.handoff import HandoffTool
from orkestra.multi_agent.subagent import DynamicSubAgentTool
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, Response, ToolCall
from orkestra.events.bus import EventBus
from orkestra.core.exceptions import HandoffException, WorkflowPausedError
from orkestra.workflows.background import WakeupService
from orkestra.events.base import TaskCompletedEvent
from tests.conftest import MockProvider

@pytest.fixture
def registry():
    return AgentRegistry()

def test_registry_cloning(registry):
    agent_template = Agent(name="TestAgent", description="Test", system_prompt="Test", provider=MockProvider([]))
    registry.register(agent_template)
    
    cloned = registry.get_agent("TestAgent")
    assert cloned is not agent_template # Should be a different instance
    assert cloned.name == "TestAgent"
    assert cloned.id == agent_template.id

@pytest.mark.asyncio
async def test_handoff_tool_raises_exception():
    bus = AsyncMock()
    tool = HandoffTool(target_agent_name="NextAgent", event_bus=bus, source_agent_name="Agent1")
    with pytest.raises(HandoffException) as exc_info:
        await tool.arun(target_agent_name="NextAgent", context_message="Hello")
        
    assert exc_info.value.target_agent_name == "NextAgent"
    assert exc_info.value.context_message == "Hello"

@pytest.mark.asyncio
async def test_subagent_tool_spawns_and_pauses():
    bus = EventBus()
    mock_registry = MagicMock()
    mock_agent = MagicMock()
    mock_agent.aadd_message = AsyncMock()
    mock_agent.astep = AsyncMock()
    mock_registry.get_agent.return_value = mock_agent
    
    tool = DynamicSubAgentTool(available_agents=["Worker"], registry=mock_registry, event_bus=bus, manager_agent_name="Manager", parent_session_id="123")
    
    # Mock AgentRunner so it doesn't crash on mocked agent
    with patch("orkestra.multi_agent.subagent.AgentRunner") as MockRunner:
        mock_runner = MagicMock()
        mock_runner.arun = AsyncMock()
        MockRunner.return_value = mock_runner
        
        # Make the subagent return a mocked message
        mock_msg = Message(role="assistant", content="Subagent result")
        mock_agent.messages = [mock_msg]
        
        result = await tool.arun(target_agent="Worker", task_description="Do work", _session_id="123", _tool_call_id="call_1", _agent_name="Manager")
        
        assert result == "Subagent result"

@pytest.mark.asyncio
async def test_orchestrator_graph_routing(registry):
    bus = EventBus()
    
    # Mock Provider for Triage (calls handoff)
    triage_provider = MockProvider([
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="c1", function_name="handoff_to_agent", function_arguments='{"target_agent": "Billing", "context_message": "Help"}')]))
    ])
    
    # Mock Provider for Billing (just returns text)
    billing_provider = MockProvider([
        Response(message=Message(role="assistant", content="Refund processed"))
    ])
    
    triage = Agent(name="Triage", description="A", system_prompt="A", provider=triage_provider, event_bus=bus)
    billing = Agent(name="Billing", description="B", system_prompt="B", provider=billing_provider, event_bus=bus)
    
    registry.register(triage)
    registry.register(billing)
    
    orchestrator = Orchestrator(registry=registry, event_bus=bus)
    orchestrator.add_handoff_edge("Triage", "Billing")
    
    result = await orchestrator.arun("Triage", "test_session_1")
    
    assert result.final_agent_name == "Billing"
    assert result.total_turns == 2

@pytest.mark.asyncio
async def test_orchestrator_swarm_routing(registry):
    bus = EventBus()
    
    # CEO delegates to worker
    ceo_provider = MockProvider([
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="c1", function_name="delegate_to_subagent", function_arguments='{"target_agent": "Worker", "task_description": "Do work"}')])),
        Response(message=Message(role="assistant", content="CEO Final Answer"))
    ])
    
    # Worker just returns text
    worker_provider = MockProvider([
        Response(message=Message(role="assistant", content="Worker done"))
    ])
    
    ceo = Agent(name="CEO", description="A", system_prompt="A", provider=ceo_provider, event_bus=bus)
    worker = Agent(name="Worker", description="B", system_prompt="B", provider=worker_provider, event_bus=bus)
    
    registry.register(ceo)
    registry.register(worker)
    
    orchestrator = Orchestrator(registry=registry, event_bus=bus)
    # No edges = Swarm mode
    
    # Because sub-agent spawning happens asynchronously in the background, we need to mock or catch it.
    # In Swarm Mode, it raises WorkflowPausedError! We need to catch it, then simulate WakeupService.
    wakeup = WakeupService(event_bus=bus, registry=registry, orchestrator=orchestrator)
    
    try:
        await orchestrator.arun("CEO", "test_swarm_1")
    except WorkflowPausedError:
        pass
        
    # Simulate Worker finishing
    await bus.apublish(TaskCompletedEvent(agent_name="CEO", session_id="test_swarm_1", tool_call_id="c1", result="Worker done"))
    
    # Wait for the wakeup service to process the event
    await asyncio.sleep(0.1)
