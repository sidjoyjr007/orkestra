import pytest
import json
from unittest.mock import MagicMock
from orkestra.core.messages import Message, ToolCall, Response
from orkestra.workflows.runner import AgentRunner
from orkestra.core.agent import Agent
from orkestra.core.tools import Tool
from tests.conftest import MockProvider

async def dummy_tool_func(**kwargs):
    return "Success"

dummy_tool = Tool(
    name="dummy_tool",
    description="Dummy",
    func=dummy_tool_func,
    schema={"type": "function", "function": {"name": "dummy_tool", "parameters": {"type": "object", "properties": {}}}}
)

@pytest.mark.asyncio
async def test_tool_loop_prevention(event_bus, memory_store):
    provider = MockProvider([
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_0", function_name="dummy_tool", function_arguments='{}')])),
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_1", function_name="dummy_tool", function_arguments='{}')])),
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_2", function_name="dummy_tool", function_arguments='{}')])),
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_3", function_name="dummy_tool", function_arguments='{}')])),
        Response(message=Message(role="assistant", content="Final answer"))
    ])
    
    agent = Agent(
        name="Bot",
        description="Mock bot",
        system_prompt="You are a mock bot.",
        provider=provider,
        memory=memory_store,
        session_id="test",
        tools=[dummy_tool],
        event_bus=event_bus
    )
    
    runner = AgentRunner(agent, event_bus=event_bus)
    
    # We will trigger the loop manually via aexecute
    tool_call_json = '{}'
    
    # Simulate the LLM repeatedly calling the exact same tool
    for i in range(4):
        # The LLM outputs an assistant message with the tool call
        tc = ToolCall(id=f"call_{i}", function_name="dummy_tool", function_arguments=tool_call_json)
        await agent.aadd_message(Message(role="assistant", content=None, tool_calls=[tc]))
        
        # The runner executes it
        await runner.executor.aexecute([tc])
        
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
