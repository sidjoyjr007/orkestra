import pytest
from unittest.mock import MagicMock
from orkestra.core.executor import ToolExecutor
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, ToolCall
from orkestra.core.tools import HostTool

@pytest.mark.asyncio
async def test_executor_aexecute():
    mock_provider = MagicMock()
    
    async def amock_tool(**kwargs):
        return "async success"
        
    tool = HostTool(name="test_tool", description="Test", schema={}, func=amock_tool)
    
    agent = Agent(name="test", description="Test", system_prompt="Sys", provider=mock_provider, tools=[tool])
    executor = ToolExecutor(agent)
    
    await executor.aexecute([ToolCall(id="t1", function_name="test_tool", function_arguments='{}')])
    
    msgs = agent.messages
    tool_msg = next((m for m in msgs if m.role == "tool" and m.name == "test_tool"), None)
    assert tool_msg is not None
    assert tool_msg.content == "async success"
