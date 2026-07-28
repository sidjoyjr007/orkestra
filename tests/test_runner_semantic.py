import pytest
from unittest.mock import MagicMock, AsyncMock
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.workflows.runner import AgentRunner

@pytest.mark.asyncio
async def test_runner_semantic_routing():
    provider = MagicMock()
    mock_registry = MagicMock()
    mock_registry.inject_semantic_tools = MagicMock()
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider)
    agent.tool_registry = mock_registry
    
    mock_response = MagicMock()
    mock_response.message = Message(role="assistant", content="Final")
    mock_response.message.tool_calls = None
    agent.astep = AsyncMock(return_value=mock_response)
    
    runner = AgentRunner(agent)
    await runner.arun()
    
    mock_registry.inject_semantic_tools.assert_called_once_with(agent)
