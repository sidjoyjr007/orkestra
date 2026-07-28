import pytest
import asyncio
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, ToolCall, Response
from orkestra.core.tools import Tool
from orkestra.workflows.runner import AgentRunner
from orkestra.core.exceptions import MaxIterationsError
from tests.conftest import MockProvider

def faulty_func(**kwargs):
    raise RuntimeError("The server is on fire!")

faulty_tool = Tool(
    name="faulty",
    description="Throws error",
    func=faulty_func,
    schema={"type": "function", "function": {"name": "faulty"}}
)

def dummy_func():
    return "done"

dummy_tool = Tool(
    name="dummy",
    description="dummy",
    func=dummy_func,
    schema={"type": "function", "function": {"name": "dummy"}}
)

@pytest.mark.asyncio
async def test_max_iterations_error(event_bus, memory_store):
    # Provider that infinitely calls the tool
    responses = [
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id=f"call_{i}", function_name="dummy", function_arguments="{}")]))
        for i in range(15)
    ]
    provider = MockProvider(responses)
    
    agent = Agent(name="Bot", description="Mock bot", system_prompt="You are a mock bot.", provider=provider, memory=memory_store, session_id="test_max_iter", tools=[dummy_tool], event_bus=event_bus)
    runner = AgentRunner(agent, event_bus=event_bus)
    
    with pytest.raises(MaxIterationsError):
        await runner.arun(max_iterations=5)
        
    assert provider.call_count == 5

@pytest.mark.asyncio
async def test_sandbox_failure_does_not_crash_runner(event_bus, memory_store):
    provider = MockProvider([
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_fail", function_name="faulty", function_arguments="{}")])),
        Response(message=Message(role="assistant", content="Final answer: I handled the error!"))
    ])
    
    agent = Agent(name="Bot", description="Mock bot", system_prompt="You are a mock bot.", provider=provider, memory=memory_store, session_id="test_sandbox_fail", tools=[faulty_tool], event_bus=event_bus)
    runner = AgentRunner(agent, event_bus=event_bus)
    
    # Should complete normally without crashing
    await runner.arun()
    
    assert agent.messages[-1].content == "Final answer: I handled the error!"
    
    # Verify the error was sent back to LLM
    tool_msgs = [m for m in agent.messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "The server is on fire!" in tool_msgs[0].content
