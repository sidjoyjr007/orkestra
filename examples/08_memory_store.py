import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.memory.in_memory import InMemoryStore
from orkestra.workflows.runner import AgentRunner

async def main():
    print("=== Orkestra: 08 InMemory Checkpointing ===\n")
    print("This example demonstrates saving and resuming agent state using InMemoryStore.")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 1. Create a Memory Store
    memory_store = InMemoryStore()
    session_id = "user_session_123"
    
    # 2. Run the First Agent Session (Populates the memory)
    print("\n--- Session 1: Storing a fact ---")
    agent_1 = Agent(
        name="MemoryBot",
        description="A bot that remembers things.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=memory_store,  # Attach memory store
        session_id=session_id # Tie it to a specific session
    )
    
    # Send a message and let the agent process it
    await agent_1.aadd_message(Message(role="user", content="Hi! My favorite color is Neon Green."))
    await agent_1.astep()
    
    for msg in agent_1.messages:
        if msg.role == "assistant":
            print(f"🤖 Agent 1: {msg.content}")

    # 3. Completely destroy the first agent
    del agent_1
    
    # 4. Create a completely new Agent object later on, but point it to the SAME memory store and session
    print("\n--- Session 2: Resuming state in a new object ---")
    agent_2 = Agent(
        name="MemoryBot",
        description="A bot that remembers things.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=memory_store,  # Same memory store
        session_id=session_id # Same session ID!
    )
    
    # Notice we do NOT pass the "favorite color" prompt again! It should pull it from memory.
    await agent_2.aadd_message(Message(role="user", content="What did I say my favorite color was?"))
    await agent_2.astep()
    
    for msg in agent_2.messages[-1:]:  # Only print the newest message
        if msg.role == "assistant":
            print(f"🤖 Agent 2: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
