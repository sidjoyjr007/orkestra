import pytest
from unittest.mock import MagicMock
from orkestra.core.agent import Agent
from orkestra.core.messages import Message

def test_agent_clone():
    provider = MagicMock()
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider)
    
    agent.add_message(Message(role="user", content="hello"))
    
    cloned = agent.clone()
    assert cloned.name == "test"
    assert cloned.description == "desc"
    assert cloned.system_prompt == "Sys"
    assert len(cloned.messages) == 1
    assert cloned.messages[0].content == "hello"
    
    # Ensure isolation
    cloned.add_message(Message(role="assistant", content="world"))
    assert len(cloned.messages) == 2
    assert len(agent.messages) == 1

@pytest.mark.asyncio
async def test_agent_aadd_message():
    provider = MagicMock()
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider)
    
    await agent.aadd_message(Message(role="user", content="hello async"))
    assert len(agent.messages) == 1
    assert agent.messages[0].content == "hello async"
    
def test_agent_memory_loading():
    provider = MagicMock()
    mock_memory = MagicMock()
    mock_memory.get_messages.return_value = [Message(role="user", content="memory_hello")]
    
    agent = Agent(name="test", description="desc", system_prompt="Sys", provider=provider, memory=mock_memory, session_id="test_sess")
    
    assert len(agent.messages) == 1
    assert agent.messages[0].content == "memory_hello"
