import pytest
import asyncio
from orkestra.memory.postgres import PostgresMemoryStore
from orkestra.core.messages import Message, ToolCall

# Use sqlite for tests to avoid needing a real Postgres DB
TEST_DB_URL = "sqlite:///test_memory.db"

@pytest.fixture(scope="module")
def memory_store():
    # Only initialize once for the module to avoid Table already defined errors
    store = PostgresMemoryStore(TEST_DB_URL)
    return store

@pytest.mark.asyncio
async def test_add_and_get_messages(memory_store):
    await memory_store.aclear("session_1")
    msg1 = Message(role="user", content="Hello")
    msg2 = Message(role="assistant", content="Hi there", tool_calls=[ToolCall(id="c1", function_name="say_hi", function_arguments="{}")])
    msg3 = Message(role="tool", content="hi", tool_call_id="c1", name="say_hi")
    
    await memory_store.aadd_message("session_1", msg1)
    await memory_store.aadd_message("session_1", msg2)
    await memory_store.aadd_message("session_1", msg3)
    
    msgs = await memory_store.aget_messages("session_1")
    assert len(msgs) == 3
    assert msgs[0].role == "user"
    assert msgs[0].content == "Hello"
    
    assert msgs[1].role == "assistant"
    assert len(msgs[1].tool_calls) == 1
    assert msgs[1].tool_calls[0].id == "c1"
    
    assert msgs[2].role == "tool"
    assert msgs[2].tool_call_id == "c1"

@pytest.mark.asyncio
async def test_clear_memory(memory_store):
    msg = Message(role="user", content="Hello")
    await memory_store.aadd_message("session_2", msg)
    
    assert len(await memory_store.aget_messages("session_2")) == 1
    await memory_store.aclear("session_2")
    assert len(await memory_store.aget_messages("session_2")) == 0

@pytest.mark.asyncio
async def test_agent_checkpoint(memory_store):
    await memory_store.asave_checkpoint("session_3", {"key": "value"})
    state = await memory_store.aload_checkpoint("session_3")
    assert state == {"key": "value"}
    
    await memory_store.asave_checkpoint("session_3", {"key": "new_value"})
    state = await memory_store.aload_checkpoint("session_3")
    assert state == {"key": "new_value"}
    
    await memory_store.aclear_checkpoint("session_3")
    assert await memory_store.aload_checkpoint("session_3") == {}
