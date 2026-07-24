import asyncio
import os
import logging
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.core.context import SlidingWindowStrategy
from orkestra.memory.in_memory import InMemoryStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("SlidingWindowDemo")

async def main():
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    memory = InMemoryStore()
    
    # We set max_messages=2.
    # This means the agent will only remember the System Prompt + the last 2 interactions.
    # If we talk to it 5 times, it will forget the first few things we said.
    strategy = SlidingWindowStrategy(max_messages=2)
    
    agent = Agent(
        name="AmnesiaBot",
        description="A bot that forgets things quickly.",
        system_prompt="You are a helpful assistant. You answer questions directly.",
        provider=provider,
        memory=memory,
        session_id="sliding_session_1",
        compaction=strategy
    )
    
    print("🤖 Agent Initialized with SlidingWindowStrategy(max_messages=2)")
    print("---------------------------------------------------------------")
    
    # Turn 1
    await agent.aadd_message(Message(role="user", content="Hi, my name is Alex. Remember my name."))
    agent.max_iterations = 1
    runner = AgentRunner(agent)
    await runner.arun()
    print(f"Alex: Hi, my name is Alex. Remember my name.")
    print(f"Bot:  {agent.messages[-1].content}\n")
    
    # Turn 2
    await agent.aadd_message(Message(role="user", content="I live in New York. Remember that too."))
    await runner.arun()
    print(f"Alex: I live in New York. Remember that too.")
    print(f"Bot:  {agent.messages[-1].content}\n")
    
    # By this point, the memory has 4 messages: User(Alex), Asst, User(NY), Asst
    # Since max_messages=2, the NEXT time we run, it will only see User(NY) and Asst!
    
    # Turn 3 - The agent should have FORGOTTEN the name because it was sliced out.
    await agent.aadd_message(Message(role="user", content="What is my name?"))
    await runner.arun()
    print(f"Alex: What is my name?")
    print(f"Bot:  {agent.messages[-1].content}\n")

if __name__ == "__main__":
    asyncio.run(main())
