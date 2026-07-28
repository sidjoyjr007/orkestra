import pytest
from unittest.mock import MagicMock, AsyncMock
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, ToolCall, Response
from orkestra.workflows.runner import AgentRunner
from orkestra.core.exceptions import MaxIterationsError
from orkestra.events.bus import EventBus

def test_runner_sync():
    provider = MagicMock()
    mock_response = MagicMock()
    mock_response.message = Message(role="assistant", content="Final response")
    mock_response.message.tool_calls = None
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider)
    agent.step = MagicMock(return_value=mock_response)
    
    runner = AgentRunner(agent)
    res = runner.run()
    
    assert res.message.content == "Final response"
    assert agent.step.called

@pytest.mark.asyncio
async def test_runner_async():
    provider = MagicMock()
    mock_response = MagicMock()
    mock_response.message = Message(role="assistant", content="Final async response")
    mock_response.message.tool_calls = None
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider)
    agent.astep = AsyncMock(return_value=mock_response)
    
    runner = AgentRunner(agent)
    res = await runner.arun()
    
    assert res.message.content == "Final async response"
    assert agent.astep.called

def test_runner_max_iterations():
    provider = MagicMock()
    
    mock_response = MagicMock()
    mock_response.message = Message(
        role="assistant", 
        content="Use tool", 
        tool_calls=[ToolCall(id="t1", function_name="dummy", function_arguments="{}")]
    )
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider, max_iterations=2)
    agent.step = MagicMock(return_value=mock_response)
    
    # We must also mock executor so it doesn't crash on 'dummy' tool
    runner = AgentRunner(agent)
    runner.executor.execute = MagicMock()
    
    with pytest.raises(MaxIterationsError):
        runner.run()

@pytest.mark.asyncio
async def test_runner_async_max_iterations():
    provider = MagicMock()
    
    mock_response = MagicMock()
    mock_response.message = Message(
        role="assistant", 
        content="Use tool", 
        tool_calls=[ToolCall(id="t1", function_name="dummy", function_arguments="{}")]
    )
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider, max_iterations=2)
    agent.astep = AsyncMock(return_value=mock_response)
    
    runner = AgentRunner(agent)
    runner.executor.aexecute = AsyncMock()
    
    with pytest.raises(MaxIterationsError):
        await runner.arun()
