import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.context import (
    KeepAllStrategy,
    SlidingWindowStrategy,
    TokenSummarizationStrategy
)
from orkestra.workflows.runner import AgentRunner
from orkestra.memory.in_memory import InMemoryStore

async def main():
    print("=== Orkestra: 13 Memory Compaction Strategies ===")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # Let's create a shared memory store for all 3 agents
    memory_store = InMemoryStore()
    
    # ---------------------------------------------------------
    # Strategy 1: KeepAllStrategy (Default)
    # Does absolutely no compaction. Context grows infinitely.
    # ---------------------------------------------------------
    print("\n--- Strategy 1: KeepAllStrategy ---")
    agent_1 = Agent(
        name="HoarderBot",
        description="Never forgets anything.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=memory_store,
        session_id="session_keep_all",
        compaction=KeepAllStrategy() # Or just omit this, as it's the default!
    )
    
    # Add 20 fake messages to history
    for i in range(20):
        await agent_1.aadd_message(Message(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}"))
        
    # The runner will prepare the context for the LLM step.
    # We can manually trigger the compaction process to see what it keeps!
    prepared_msgs_1 = await agent_1.compaction.aprocess(agent_1.messages, agent_1.system_prompt, agent_1.memory, agent_1.session_id)
    print(f"KeepAll retained {len(prepared_msgs_1)} total messages in context.")
    
    # ---------------------------------------------------------
    # Strategy 2: SlidingWindowStrategy
    # Keeps exactly N recent messages. Oldest are truncated.
    # ---------------------------------------------------------
    print("\n--- Strategy 2: SlidingWindowStrategy ---")
    agent_2 = Agent(
        name="GoldfishBot",
        description="Only remembers recent things.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=memory_store,
        session_id="session_sliding",
        compaction=SlidingWindowStrategy(max_messages=4) # Only keep the last 4 messages!
    )
    
    for i in range(20):
        await agent_2.aadd_message(Message(role="user" if i % 2 == 0 else "assistant", content=f"Message {i}"))
        
    prepared_msgs_2 = await agent_2.compaction.aprocess(agent_2.messages, agent_2.system_prompt, agent_2.memory, agent_2.session_id)
    print(f"SlidingWindow retained {len(prepared_msgs_2)} messages in context (1 System Prompt + 4 recent).")
    print(f"Oldest retained message: {prepared_msgs_2[1].content}") # Index 0 is the system prompt
    
    # ---------------------------------------------------------
    # Strategy 3: TokenSummarizationStrategy
    # Summarizes history via LLM when max_tokens is exceeded.
    # ---------------------------------------------------------
    print("\n--- Strategy 3: TokenSummarizationStrategy ---")
    print("This will execute a live LLM call to summarize the 20 messages!")
    
    agent_3 = Agent(
        name="ArchivistBot",
        description="Summarizes old history.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=memory_store,
        session_id="session_summarization",
        compaction=TokenSummarizationStrategy(max_tokens=20, provider=provider) # Very low token limit to force summary
    )
    
    for i in range(20):
        await agent_3.aadd_message(Message(role="user" if i % 2 == 0 else "assistant", content=f"Important conversation detail {i}"))
        
    prepared_msgs_3 = await agent_3.compaction.aprocess(agent_3.messages, agent_3.system_prompt, agent_3.memory, agent_3.session_id)
    
    print(f"TokenSummarization retained {len(prepared_msgs_3)} messages (1 System Prompt, 1 Summary System Prompt, 2 recent raw messages).")
    print(f"\n[Generated Summary]:\n{prepared_msgs_3[1].content}\n")
    print(f"[Recent Raw 1]: {prepared_msgs_3[2].content}")
    print(f"[Recent Raw 2]: {prepared_msgs_3[3].content}")

if __name__ == "__main__":
    asyncio.run(main())
