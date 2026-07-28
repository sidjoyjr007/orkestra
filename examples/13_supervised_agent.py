import asyncio
import os
from orkestra.core.agent import Agent
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.multi_agent.supervisor import SupervisedAgent
from orkestra.multi_agent.orchestrator import Orchestrator
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.events.bus import EventBus
from orkestra.core.messages import Message

async def main():
    # Make sure GEMINI_API_KEY is set in your environment
    gemini = GeminiProvider(model_name="gemini-2.5-flash")
    
    # 1. Define the Worker Agent
    # We purposefully give the worker a vague instruction to encourage mistakes
    junior_writer = Agent(
        name="junior_writer",
        description="A junior copywriter who writes very short product descriptions.",
        system_prompt="You are a junior copywriter. Write a 1-sentence product description for whatever the user asks for.",
        provider=gemini
    )
    
    # 2. Define the Critic Agent
    # The critic enforces strict quality rules
    senior_editor = Agent(
        name="senior_editor",
        description="A strict senior editor.",
        system_prompt=(
            "You are a strict senior editor. The junior writer will provide a product description. "
            "Your strict rule: The description MUST contain the word 'EXCITING' in all caps. "
            "If it does not contain 'EXCITING', reject it with feedback telling them to add it. "
            "If it DOES contain 'EXCITING', you must output EXACTLY the word 'APPROVED' and nothing else."
        ),
        provider=gemini
    )
    
    # 3. Wrap the worker and critic in a SupervisedAgent
    supervised_writer = SupervisedAgent(
        worker_agent=junior_writer,
        critic_agent=senior_editor,
        max_retries=3
    )
    
    supervised_writer.session_id = "demo_session"
    await supervised_writer.aadd_message(Message(role="user", content="Write a description for a Smart Coffee Mug."))
    
    # 4. Set up the Orchestrator
    registry = AgentRegistry()
    registry.register(supervised_writer)
    
    orchestrator = Orchestrator(registry=registry, event_bus=EventBus())
    
    print("--- Starting Supervised Workflow ---")
    print("Task: Write a description for a 'Smart Coffee Mug'\n")
    
    # Run the orchestrator!  
    # Notice how we route to "junior_writer" (the name of the worker agent)
    # The SupervisedAgent handles the internal critic loop completely transparently!
    await orchestrator.arun(entry_agent_name="junior_writer", session_id="demo_session", max_turns=1)
    
    # Let's see the final result that was approved
    final_agent = orchestrator.active_agent
    
    print("\n--- Final Approved Result ---")
    for msg in final_agent.messages:
        if msg.role == "assistant":
            print(f"[{msg.name or 'Assistant'}]: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
