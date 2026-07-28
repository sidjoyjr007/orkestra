import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.memory.postgres import PostgresMemoryStore

async def main():
    print("=== Orkestra: 09 Postgres Checkpointing ===\n")
    print("This example demonstrates saving and resuming agent state persistently in PostgreSQL.\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    db_url = os.getenv("POSTGRES_URL", "postgresql://orkestra:orkestra@localhost:5432/orkestra")
    
    try:
        # 1. Connect to PostgreSQL (Requires asyncpg and psycopg2)
        # To run locally: docker run --name orkestra-pg -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres
        postgres_store = PostgresMemoryStore(db_url)
    except Exception as e:
        print(f"❌ Failed to connect to PostgreSQL: {e}")
        print("\nTo run this example, you need a local Postgres database running.")
        print("Run this command in a terminal, then try again:")
        print("    docker run --name orkestra-pg -e POSTGRES_PASSWORD=password -p 5432:5432 -d postgres")
        print("\nMake sure to install drivers: pip install asyncpg psycopg2-binary sqlalchemy")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    session_id = "user_pg_session_999"
    
    print("\n--- Session 1: Storing a fact in DB ---")
    agent_1 = Agent(
        name="DBBot",
        description="A bot that persists memory to PostgreSQL.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=postgres_store,  # Attach postgres store
        session_id=session_id
    )
    
    await agent_1.aadd_message(Message(role="user", content="Hi! My secret code is 4242."))
    await agent_1.astep()
    
    for msg in agent_1.messages:
        if msg.role == "assistant":
            print(f"🤖 Agent 1: {msg.content}")

    # Destroy the agent
    del agent_1
    
    print("\n--- Session 2: Resuming state from DB into a new object ---")
    agent_2 = Agent(
        name="DBBot",
        description="A bot that persists memory to PostgreSQL.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=postgres_store,  # Same DB store
        session_id=session_id
    )
    
    # We do NOT pass the secret code again. It pulls the history straight from Postgres!
    await agent_2.aadd_message(Message(role="user", content="What was my secret code?"))
    await agent_2.astep()
    
    for msg in agent_2.messages[-1:]: 
        if msg.role == "assistant":
            print(f"🤖 Agent 2: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
