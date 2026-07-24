import pytest
from orkestra.memory.postgres import PostgresMemoryStore
from orkestra.core.messages import Message

@pytest.mark.asyncio
async def test_session_segregation():
    db_url = "postgresql://orkestra:orkestra@localhost:5432/orkestra"
    memory = PostgresMemoryStore(db_url)
    
    await memory.aclear("session_A")
    await memory.aclear("session_B")
    
    await memory.aadd_message("session_A", Message(role="user", content="Hello A"))
    await memory.aadd_message("session_B", Message(role="user", content="Hello B"))
    
    messages_a = await memory.aget_messages("session_A")
    messages_b = await memory.aget_messages("session_B")
    
    assert len(messages_a) == 1
    assert messages_a[0].content == "Hello A"
    
    assert len(messages_b) == 1
    assert messages_b[0].content == "Hello B"

@pytest.mark.asyncio
async def test_memory_clear():
    db_url = "postgresql://orkestra:orkestra@localhost:5432/orkestra"
    memory = PostgresMemoryStore(db_url)
    
    await memory.aadd_message("session_C", Message(role="user", content="Hello C"))
    await memory.aadd_message("session_D", Message(role="user", content="Hello D"))
    
    await memory.aclear("session_C")
    
    messages_c = await memory.aget_messages("session_C")
    messages_d = await memory.aget_messages("session_D")
    
    assert len(messages_c) == 0
    assert len(messages_d) >= 1
