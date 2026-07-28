import pytest
from unittest.mock import MagicMock, AsyncMock
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, ToolCall, Response
from orkestra.workflows.runner import AgentRunner
from orkestra.events.bus import EventBus
from orkestra.events.base import WorkflowStarted, WorkflowCompleted

def test_runner_unanswered_tools():
    provider = MagicMock()
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider)
    runner = AgentRunner(agent)
    
    # Empty messages
    assert runner._get_unanswered_tools() == []
    
    # Last message not assistant
    agent.add_message(Message(role="user", content="Hello"))
    assert runner._get_unanswered_tools() == []
    
    # Assistant with tool calls
    agent.add_message(Message(
        role="assistant", 
        content="Use tool", 
        tool_calls=[
            ToolCall(id="t1", function_name="f1", function_arguments="{}"),
            ToolCall(id="t2", function_name="f2", function_arguments="{}")
        ]
    ))
    
    # One is answered
    agent.add_message(Message(role="tool", content="Done", tool_call_id="t1"))
    
    unanswered = runner._get_unanswered_tools()
    assert len(unanswered) == 1
    assert unanswered[0].id == "t2"
    
def test_runner_sync_unanswered_tools_execution():
    provider = MagicMock()
    
    # Setup agent with unanswered tools
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider, max_iterations=2)
    agent.add_message(Message(
        role="assistant", 
        content="Use tool", 
        tool_calls=[ToolCall(id="t1", function_name="f1", function_arguments="{}")]
    ))
    
    # Next step returns no tools to end loop
    mock_response = MagicMock()
    mock_response.message = Message(role="assistant", content="Final")
    mock_response.message.tool_calls = None
    agent.step = MagicMock(return_value=mock_response)
    
    def mock_execute(tool_calls):
        agent.add_message(Message(role="tool", content="done", tool_call_id=tool_calls[0].id))
        
    runner = AgentRunner(agent)
    runner.executor.execute = MagicMock(side_effect=mock_execute)
    
    runner.run()
    
    # Execute should be called for unanswered tools first
    runner.executor.execute.assert_called()

def test_runner_sync_event_and_memory():
    provider = MagicMock()
    bus = EventBus()
    bus.publish = MagicMock()
    
    mock_memory = MagicMock()
    mock_memory.asave_checkpoint = AsyncMock()
    
    mock_response = MagicMock()
    mock_response.message = Message(role="assistant", content="Final")
    mock_response.message.tool_calls = None
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider, memory=mock_memory)
    agent.step = MagicMock(return_value=mock_response)
    
    runner = AgentRunner(agent, event_bus=bus)
    runner.run()
    
    # Should publish WorkflowStarted and WorkflowCompleted
    assert bus.publish.call_count >= 2
    mock_memory.asave_checkpoint.assert_called()

@pytest.mark.asyncio
async def test_runner_async_event_and_memory():
    provider = MagicMock()
    bus = EventBus()
    bus.apublish = AsyncMock()
    
    mock_memory = MagicMock()
    mock_memory.asave_checkpoint = AsyncMock()
    
    mock_response = MagicMock()
    mock_response.message = Message(role="assistant", content="Final")
    mock_response.message.tool_calls = None
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider, memory=mock_memory)
    agent.astep = AsyncMock(return_value=mock_response)
    
    runner = AgentRunner(agent, event_bus=bus)
    await runner.arun()
    
    assert bus.apublish.call_count >= 2
    mock_memory.asave_checkpoint.assert_called()

@pytest.mark.asyncio
async def test_runner_async_unanswered_tools_execution():
    provider = MagicMock()
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider, max_iterations=2)
    agent.add_message(Message(
        role="assistant", 
        content="Use tool", 
        tool_calls=[ToolCall(id="t1", function_name="f1", function_arguments="{}")]
    ))
    
    mock_response = MagicMock()
    mock_response.message = Message(role="assistant", content="Final")
    mock_response.message.tool_calls = None
    agent.astep = AsyncMock(return_value=mock_response)
    
    async def mock_aexecute(tool_calls):
        await agent.aadd_message(Message(role="tool", content="done", tool_call_id=tool_calls[0].id))
        
    runner = AgentRunner(agent)
    runner.executor.aexecute = AsyncMock(side_effect=mock_aexecute)
    
    await runner.arun()
    
    runner.executor.aexecute.assert_called()
