import pytest
import json
from unittest.mock import MagicMock
from orkestra.core.messages import Message, ToolCall
from orkestra.workflows.runner import AgentRunner

@pytest.mark.asyncio
async def test_tool_loop_prevention():
    # 1. Setup mock agent and tool
    agent = MagicMock()
    agent.name = "TestAgent"
    agent.messages = []
    
    # We will track messages added to the agent
    def add_message(msg):
        agent.messages.append(msg)
    
    agent.add_message.side_effect = add_message
    agent.aadd_message.side_effect = add_message
    
    # Mock tool
    mock_tool = MagicMock()
    mock_tool.name = "dummy_tool"
    async def arun(**kwargs):
        return "Success"
    mock_tool.arun = arun
    agent.tools = [mock_tool]
    
    runner = AgentRunner(agent)
    
    tool_call_json = '{"arg": 1}'
    
    # Simulate the LLM repeatedly calling the exact same tool
    for i in range(4):
        # The LLM outputs an assistant message with the tool call
        tc = ToolCall(id=f"call_{i}", function_name="dummy_tool", function_arguments=tool_call_json)
        agent.messages.append(Message(role="assistant", content=None, tool_calls=[tc]))
        
        # The runner executes it
        await runner._aexecute_tool_calls([tc])
        
    # There should be 4 tool response messages added
    tool_responses = [m for m in agent.messages if m.role == "tool"]
    assert len(tool_responses) == 4
    
    # The first two should have executed successfully
    assert tool_responses[0].content == "Success"
    assert tool_responses[1].content == "Success"
    
    # The 3rd and 4th should have been intercepted!
    assert "SYSTEM WARNING" in tool_responses[2].content
    assert "3 times" in tool_responses[2].content
    
    assert "SYSTEM WARNING" in tool_responses[3].content
    assert "4 times" in tool_responses[3].content
