import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.events.bus import EventBus
from orkestra.multi_agent.orchestrator import Orchestrator
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.workflows.background import WakeupService
from orkestra.core.background_tool import BackgroundTool

# Simulate a slow, 5-second background task
async def slow_data_processing(data: str, **kwargs) -> str:
    print(f"   [Background Task Started] Processing '{data}'... this will take 5 seconds.")
    await asyncio.sleep(5)
    print(f"   [Background Task Completed]")
    return f"Processed data: {data.upper()}"

async def main():
    print("=== Orkestra: 23 Long-Running Workflows & WakeupService ===")
    print("Demonstrating how an agent can spawn a long-running background task, go to sleep, and be automatically awakened by the WakeupService when the task finishes.\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    event_bus = EventBus()
    registry = AgentRegistry()
    
    # 1. Create a background tool wrapper
    bg_tool = BackgroundTool(
        name="process_data_async",
        description="Processes data asynchronously. You will go to sleep until this finishes.",
        target_coroutine=slow_data_processing,
        event_bus=event_bus
    )
    
    # 2. Create the Agent
    agent = Agent(
        name="AsyncWorker",
        description="Processes data asynchronously.",
        system_prompt="You are an async worker. Use the process_data_async tool to process the user's string. Once the system wakes you up with the result, tell the user the final output.",
        provider=provider,
        tools=[bg_tool],
        id="async_1",
        event_bus=event_bus
    )
    registry.register(agent)
    
    # 3. Setup Orchestrator and WakeupService
    orchestrator = Orchestrator(registry=registry, event_bus=event_bus)
    wakeup_service = WakeupService(event_bus=event_bus, registry=registry, orchestrator=orchestrator)
    
    # 4. Start the initial run
    session_id = "async_session_1"
    user_prompt = "Please process the string 'hello world'."
    print(f"User: {user_prompt}\n")
    
    agent.messages.append(Message(role="user", content=user_prompt))
    
    print("--- Initial Run ---")
    try:
        # The agent will call the background tool, which raises WorkflowPausedError
        await orchestrator.arun(entry_agent_name="AsyncWorker", session_id=session_id, max_turns=5)
    except Exception as e:
        print(f"Orchestrator paused natively with: {type(e).__name__}")
        
    print("\n--- Main Thread is Free! (Doing other work...) ---")
    
    # Wait for the background task to finish and the WakeupService to resume the orchestrator
    # We'll just sleep for 8 seconds to give the background task (5s) and LLM response (2s) time to finish.
    await asyncio.sleep(8)
    
    print("\n--- Final Check ---")
    # At this point, the WakeupService should have fired the Orchestrator again and completed the flow!
    print("Workflow complete.")

if __name__ == "__main__":
    asyncio.run(main())
