import pytest
import os
import shutil
from orkestra.multi_agent.snapshot import SnapshotManager
from orkestra.multi_agent.orchestrator import Orchestrator
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.multi_agent.scratchpad import SharedScratchpad
from orkestra.events.bus import EventBus
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, ToolCall
from unittest.mock import MagicMock

@pytest.fixture
def temp_checkpoint_dir():
    dir_name = ".test_checkpoints"
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)
    yield dir_name
    if os.path.exists(dir_name):
        shutil.rmtree(dir_name)

def test_snapshot_manager_save_load(temp_checkpoint_dir):
    manager = SnapshotManager(checkpoint_dir=temp_checkpoint_dir)
    registry = AgentRegistry()
    
    # Create an agent with some history
    agent = Agent(name="agent_a", description="a", system_prompt="a", provider=MagicMock())
    agent.session_id = "test_sess"
    agent.messages = [Message(role="user", content="hello"), Message(role="assistant", content="hi")]
    agent.usage = {"prompt_tokens": 10, "completion_tokens": 5}
    registry.register(agent)
    
    scratchpad = SharedScratchpad()
    scratchpad.set("state", "active")
    
    active_agents = {"agent_a": agent}
    
    # Save checkpoint
    manager.save_checkpoint(
        checkpoint_id="chk1",
        active_agents=active_agents,
        current_agent_name="agent_b",
        scratchpad=scratchpad,
        handoff_state={"target": "agent_b", "context": "go do X"}
    )
    
    # Load checkpoint
    new_scratchpad = SharedScratchpad()
    state = manager.load_checkpoint("chk1", registry, new_scratchpad)
    
    assert state["current_agent_name"] == "agent_b"
    assert state["handoff_state"]["context"] == "go do X"
    assert new_scratchpad.get("state") == "active"
    
    restored_agent = state["active_agents"]["agent_a"]
    assert restored_agent.session_id == "test_sess"
    assert len(restored_agent.messages) == 2
    assert restored_agent.messages[1].content == "hi"
    assert restored_agent.usage["prompt_tokens"] == 10

@pytest.mark.asyncio
async def test_orchestrator_resume(temp_checkpoint_dir):
    registry = AgentRegistry()
    registry.register(Agent(name="agent_a", description="a", system_prompt="a", provider=MagicMock()))
    
    event_bus = EventBus()
    orchestrator = Orchestrator(registry=registry, event_bus=event_bus, checkpoint_dir=temp_checkpoint_dir)
    
    # Manually save a checkpoint as if it was created during a run
    orchestrator.active_agents_dict["agent_a"] = registry.get_agent("agent_a")
    orchestrator.snapshot_manager.save_checkpoint(
        checkpoint_id="resume_test",
        active_agents=orchestrator.active_agents_dict,
        current_agent_name="agent_a",
        handoff_state={"target": "agent_a", "context": "resume me", "tool_call_id": "call_123"}
    )
    
    # Mock runner so it doesn't actually call LLMs
    with pytest.MonkeyPatch.context() as m:
        m.setattr("orkestra.multi_agent.orchestrator.AgentRunner.arun", _mock_arun)
        
        # Resume orchestrator
        res = await orchestrator.resume("resume_test", max_turns=1)
        
    assert res.final_agent_name == "agent_a"
    assert orchestrator._handoff_context is None # Consumed

async def _mock_arun(*args, **kwargs):
    pass

def test_snapshot_manager_clear(temp_checkpoint_dir):
    manager = SnapshotManager(checkpoint_dir=temp_checkpoint_dir)
    registry = AgentRegistry()
    
    # Save a dummy checkpoint
    manager.save_checkpoint(
        checkpoint_id="dummy_clear",
        active_agents={},
        current_agent_name="agent_x"
    )
    
    filepath = os.path.join(temp_checkpoint_dir, "dummy_clear.json")
    assert os.path.exists(filepath)
    
    manager.clear_checkpoints()
    
    assert not os.path.exists(filepath)
