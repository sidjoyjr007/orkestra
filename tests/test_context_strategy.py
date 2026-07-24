import pytest
import os
import shutil
import asyncio
from orkestra.core.messages import Message, ToolCall, Response
from orkestra.core.context import KeepAllStrategy, SlidingWindowStrategy, TokenSummarizationStrategy
from orkestra.core.tools import Tool
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from tests.conftest import MockProvider

@pytest.mark.asyncio
async def test_sliding_window_strategy():
    strategy = SlidingWindowStrategy(max_messages=2)
    messages = [
        Message(role="system", content="System"),
        Message(role="user", content="Msg 1"),
        Message(role="assistant", content="Msg 2"),
        Message(role="user", content="Msg 3")
    ]
    
    result = await strategy.aprocess(messages, "System", None, "test")
    assert len(result) == 3
    assert result[0].role == "system"
    assert result[1].content == "Msg 2"
    assert result[2].content == "Msg 3"

@pytest.mark.asyncio
async def test_token_summarization_strategy(memory_store):
    provider = MockProvider([Response(message=Message(role="assistant", content="MOCK SUMMARY"))])
    strategy = TokenSummarizationStrategy(max_tokens=10, provider=provider)
    
    messages = [
        Message(role="user", content="A very long message 1"), # 5 tokens
        Message(role="assistant", content="A very long message 2"), # 5 tokens
        Message(role="user", content="A very long message 3"), # 5 tokens
        Message(role="assistant", content="A very long message 4") # 5 tokens
    ] # Total 20 tokens -> Exceeds max_tokens=10
    
    result = await strategy.aprocess(messages, "System", memory_store, "test_session")
    
    # Keeps System + Summary + Last 2
    assert len(result) == 4
    assert result[0].role == "system"
    assert result[1].role == "system"
    assert "MOCK SUMMARY" in result[1].content
    assert result[2].content == "A very long message 3"
    assert result[3].content == "A very long message 4"
    
    # Check DB was mutated
    db_msgs = memory_store.get_messages("test_session")
    assert len(db_msgs) == 3 # Summary + last 2

def dummy_long_func():
    return "X" * 1000

@pytest.mark.asyncio
async def test_tool_truncation_and_dynamic_injection(event_bus, memory_store):
    long_tool = Tool(
        name="fetch_data",
        description="Fetch a lot of data",
        func=dummy_long_func,
        schema={"type": "function", "function": {"name": "fetch_data"}},
        max_result_length=10 # Truncate to 10 chars
    )
    
    # Provider asks for tool, then asks for read_file_chunk
    provider = MockProvider([
        Response(message=Message(role="assistant", tool_calls=[ToolCall(id="call_99", function_name="fetch_data", function_arguments="{}")])),
        # Immediately returns success to stop infinite loop
        Response(message=Message(role="assistant", content="Done"))
    ])
    
    agent = Agent(
        name="Bot",
        description="Mock",
        system_prompt="Mock",
        provider=provider,
        memory=memory_store,
        session_id="test_truncation",
        tools=[long_tool],
        event_bus=event_bus,
        compaction=KeepAllStrategy()
    )
    
    runner = AgentRunner(agent, event_bus=event_bus)
    await runner.arun()
    
    # Check that artifact was created
    artifact_path = f"/tmp/orkestra_artifacts/test_truncation/call_99.txt"
    assert os.path.exists(artifact_path)
    with open(artifact_path, "r") as f:
        assert len(f.read()) == 1000
        
    # Check that it was truncated in memory
    tool_msg = agent.messages[1]
    assert len(tool_msg.content) < 200 # 10 chars + warning
    assert "[TRUNCATED]" in tool_msg.content
    assert artifact_path in tool_msg.content
    
    # Manually step to check if read_file_chunk gets injected
    provider.call_count = 0
    # Next step will check prepared messages. Let's spy on provider.agenerate to see kwargs
    async def mock_agenerate(*args, **kwargs):
        assert "tools" in kwargs
        tool_names = [t["function"]["name"] for t in kwargs["tools"]]
        assert "read_file_chunk" in tool_names
        return Response(message=Message(role="assistant", content="Success"))
        
    provider.agenerate = mock_agenerate
    await agent.astep()
    
    # Cleanup
    shutil.rmtree("/tmp/orkestra_artifacts/test_truncation")
