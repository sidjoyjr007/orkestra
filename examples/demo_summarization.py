import asyncio
import os
import logging
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.core.context import TokenSummarizationStrategy
from orkestra.memory.in_memory import InMemoryStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SummarizationDemo")

async def main():
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # We set max_tokens=25 to force it to summarize almost immediately.
    strategy = TokenSummarizationStrategy(max_tokens=25, provider=provider)
    memory = InMemoryStore()
    
    agent = Agent(
        name="SummaryBot",
        description="A bot that compresses its own memory.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=memory,
        session_id="summary_session_1",
        compaction=strategy
    )
    
    print("🤖 Agent Initialized with TokenSummarizationStrategy(max_tokens=25)")
    print("------------------------------------------------------------------")
    
    runner = AgentRunner(agent)
    
    # Turn 1
    long_msg = "Hello! My name is Alex. I am a software engineer working on a Python framework called Orkestra. It's really cool."
    await agent.aadd_message(Message(role="user", content=long_msg))
    await runner.arun()
    
    print(f"User: {long_msg}")
    print(f"Bot:  {agent.messages[-1].content}\n")
    
    # Turn 2
    long_msg_2 = "I also have a pet dog named Max. Max loves playing fetch in central park on Sundays."
    await agent.aadd_message(Message(role="user", content=long_msg_2))
    await runner.arun()
    
    print(f"User: {long_msg_2}")
    print(f"Bot:  {agent.messages[-1].content}\n")
    
    # Turn 3 - This will trigger the compaction because we exceeded tokens AND have >= 4 non-system messages!
    long_msg_3 = "By the way, Orkestra is highly scalable. It uses Postgres for memory management!"
    await agent.aadd_message(Message(role="user", content=long_msg_3))
    
    print("... Calling LLM (This will trigger a background Summarization call!) ...")
    await runner.arun()
    
    print(f"User: {long_msg_3}")
    print(f"Bot:  {agent.messages[-1].content}\n")
    
    print("------------------------------------------------------------------")
    print("🔍 Let's look at what is ACTUALLY stored in the Database now:")
    db_messages = memory.get_messages("summary_session_1")
    for m in db_messages:
        print(f"[{m.role.upper()}]: {m.content[:100]}...")
        
    print("\nNotice how the old messages were DELETED from the DB and replaced with a dense 'System' summary!")

if __name__ == "__main__":
    asyncio.run(main())
