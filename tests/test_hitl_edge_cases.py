import pytest
import asyncio
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, ToolCall, Response
from orkestra.core.tools import Tool
from orkestra.workflows.runner import AgentRunner
from orkestra.events.base import HumanApprovalRequested, HumanApprovalProvided
from tests.conftest import MockProvider

def dangerous_func(version: str, **kwargs):
    return f"Deployed {version}"

dangerous_tool = Tool(
    name="deploy",
    description="Deploys code",
    func=dangerous_func,
    schema={"type": "function", "function": {"name": "deploy", "parameters": {"type": "object", "properties": {"version": {"type": "string"}}}}},
    requires_approval=True
)

@pytest.mark.asyncio
async def test_hitl_graceful_suspension_and_resume_approved(event_bus, memory_store):
    provider = MockProvider([
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_1", function_name="deploy", function_arguments='{"version": "v1"}')])),
        Response(message=Message(role="assistant", content="Final answer: Deployed v1"))
    ])
    
    agent = Agent(name="Bot", description="Mock bot", system_prompt="You are a mock bot.", provider=provider, memory=memory_store, session_id="test", tools=[dangerous_tool], event_bus=event_bus)
    runner = AgentRunner(agent, event_bus=event_bus)
    
    # Run in background so it can pause
    run_task = asyncio.create_task(runner.arun())
    
    # Wait for the future to be registered
    await asyncio.sleep(0.1)
    
    assert "call_1" in runner.executor._pending_approvals
    
    # Simulate webhook
    await event_bus.apublish(HumanApprovalProvided(tool_call_id="call_1", result="[HUMAN APPROVED] user says yes"))
    
    # Runner should complete
    await run_task
    
    assert agent.messages[-1].content == "Final answer: Deployed v1"
    # Ensure the tool message was recorded
    tool_msgs = [m for m in agent.messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "Deployed v1" in tool_msgs[0].content # the python tool executed

@pytest.mark.asyncio
async def test_hitl_human_rejected(event_bus, memory_store):
    provider = MockProvider([
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_2", function_name="deploy", function_arguments='{"version": "v2"}')])),
        Response(message=Message(role="assistant", content="Final answer: Denied"))
    ])
    
    agent = Agent(name="Bot", description="Mock bot", system_prompt="You are a mock bot.", provider=provider, memory=memory_store, session_id="test2", tools=[dangerous_tool], event_bus=event_bus)
    runner = AgentRunner(agent, event_bus=event_bus)
    
    run_task = asyncio.create_task(runner.arun())
    await asyncio.sleep(0.1)
    
    assert "call_2" in runner.executor._pending_approvals
    
    await event_bus.apublish(HumanApprovalProvided(tool_call_id="call_2", result="[HUMAN REJECTED] Not allowed"))
    
    await run_task
    
    assert agent.messages[-1].content == "Final answer: Denied"
    tool_msgs = [m for m in agent.messages if m.role == "tool"]
    assert len(tool_msgs) == 1
    assert "Not allowed" in tool_msgs[0].content

@pytest.mark.asyncio
async def test_hitl_stateless_crash_resume(event_bus, memory_store):
    provider = MockProvider([
        # The agent asks for tool
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_3", function_name="deploy", function_arguments='{"version": "v3"}')])),
        # Immediately responds after resuming
        Response(message=Message(role="assistant", content="Final answer: Crash recovered!"))
    ])
    
    agent = Agent(name="Bot", description="Mock bot", system_prompt="You are a mock bot.", provider=provider, memory=memory_store, session_id="test3", tools=[dangerous_tool], event_bus=event_bus)
    
    # 1. Simulate the first run that crashed
    runner1 = AgentRunner(agent, event_bus=event_bus)
    task1 = asyncio.create_task(runner1.arun())
    await asyncio.sleep(0.1)
    task1.cancel() # simulate crash!
    
    # 2. Webhook comes in and saves straight to DB
    await agent.aapprove_tool(tool_call_id="call_3", tool_name="deploy", result="[HUMAN APPROVED] Success DB")
    
    # 3. New Runner starts up (cron/retry)
    runner2 = AgentRunner(agent, event_bus=event_bus)
    await runner2.arun() # Should NOT pause!
    
    assert agent.messages[-1].content == "Final answer: Crash recovered!"
