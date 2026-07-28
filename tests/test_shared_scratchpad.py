import pytest
from orkestra.multi_agent.scratchpad import SharedScratchpad, ReadScratchpadTool, WriteScratchpadTool
from orkestra.multi_agent.orchestrator import Orchestrator
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.events.bus import EventBus
from orkestra.core.agent import Agent

def test_shared_scratchpad_basics():
    scratchpad = SharedScratchpad()
    scratchpad.set("key1", "val1")
    assert scratchpad.get("key1") == "val1"
    
    scratchpad.set("key2", {"nested": True})
    assert scratchpad.get("key2") == {"nested": True}
    
    assert set(scratchpad.list_keys()) == {"key1", "key2"}
    
    scratchpad.delete("key1")
    assert scratchpad.get("key1") is None

@pytest.mark.asyncio
async def test_scratchpad_tools():
    scratchpad = SharedScratchpad()
    write_tool = WriteScratchpadTool(scratchpad)
    read_tool = ReadScratchpadTool(scratchpad)
    
    # Write a value
    res = await write_tool.arun("mission", "top secret")
    assert "Successfully wrote" in res
    
    # Read the value
    res = await read_tool.arun("mission")
    assert res == "top secret"
    
    # Read non-existent
    res = await read_tool.arun("unknown")
    assert "not found" in res
    assert "mission" in res

def test_orchestrator_scratchpad_injection():
    registry = AgentRegistry()
    from unittest.mock import MagicMock
    registry.register(Agent(name="agent_a", description="desc", system_prompt="prompt", provider=MagicMock()))
    
    event_bus = EventBus()
    scratchpad = SharedScratchpad()
    
    orchestrator = Orchestrator(registry=registry, event_bus=event_bus, scratchpad=scratchpad)
    
    # We just run 0 turns to let it initialize and inject tools, but 0 turns will just break.
    # We can mock runner to avoid running the llm
    with pytest.MonkeyPatch.context() as m:
        m.setattr("orkestra.multi_agent.orchestrator.AgentRunner.arun", _mock_arun)
        
        import asyncio
        asyncio.run(orchestrator.arun("agent_a", max_turns=1))
        
    agent = orchestrator.active_agent
    tool_names = [t.name for t in agent.tools]
    assert "read_scratchpad" in tool_names
    assert "write_scratchpad" in tool_names

async def _mock_arun(*args, **kwargs):
    pass
