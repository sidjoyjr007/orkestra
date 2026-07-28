import pytest
import asyncio
from unittest.mock import patch, MagicMock, AsyncMock
from orkestra.multi_agent.subagent import DynamicParallelSubAgentTool
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.events.bus import EventBus
from orkestra.core.messages import Message

@pytest.mark.asyncio
async def test_parallel_subagent_tool():
    registry = AgentRegistry()
    event_bus = EventBus()
    
    # We will mock the single tool's arun to return predefined values for different agents
    tool = DynamicParallelSubAgentTool(
        available_agents=["agent_a", "agent_b", "agent_c"],
        registry=registry,
        event_bus=event_bus,
        manager_agent_name="manager",
        parent_session_id="session1"
    )
    
    async def mock_single_arun(target_agent, task_description, **kwargs):
        await asyncio.sleep(0.01) # simulate async work
        return f"Result from {target_agent}: {task_description}"
        
    tool._single_tool.arun = AsyncMock(side_effect=mock_single_arun)
    
    delegations = [
        {"target_agent": "agent_a", "task_description": "task 1"},
        {"target_agent": "agent_b", "task_description": "task 2"}
    ]
    
    result = await tool.arun(delegations=delegations)
    
    assert "Parallel Execution Report for 2 tasks" in result
    assert "Result from agent_a: task 1" in result
    assert "Result from agent_b: task 2" in result
    assert tool._single_tool.arun.call_count == 2
    
@pytest.mark.asyncio
async def test_parallel_subagent_tool_with_error():
    registry = AgentRegistry()
    event_bus = EventBus()
    
    tool = DynamicParallelSubAgentTool(
        available_agents=["agent_a", "agent_b"],
        registry=registry,
        event_bus=event_bus,
        manager_agent_name="manager",
        parent_session_id="session1"
    )
    
    async def mock_single_arun(target_agent, task_description, **kwargs):
        if target_agent == "agent_a":
            raise ValueError("Intentional crash")
        return "Success"
        
    tool._single_tool.arun = AsyncMock(side_effect=mock_single_arun)
    
    delegations = [
        {"target_agent": "agent_a", "task_description": "task 1"},
        {"target_agent": "agent_b", "task_description": "task 2"}
    ]
    
    result = await tool.arun(delegations=delegations)
    
    # gather(return_exceptions=True) should capture the error and format it
    assert "Error during execution: Intentional crash" in result
    assert "Success" in result
    
@pytest.mark.asyncio
async def test_parallel_subagent_invalid_input():
    registry = AgentRegistry()
    tool = DynamicParallelSubAgentTool(
        available_agents=["agent_a"],
        registry=registry,
        event_bus=EventBus(),
        manager_agent_name="m",
        parent_session_id="s"
    )
    
    # Missing delegations
    assert "Error: No delegations provided" in await tool.arun(delegations=[])
    
    # Missing required keys
    assert "Error: Invalid delegations format" in await tool.arun(delegations=[{"wrong": "key"}])
