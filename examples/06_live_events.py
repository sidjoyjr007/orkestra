import asyncio
import os
import time
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.events.bus import EventBus
from orkestra.events.base import ToolExecutionStarted, ToolExecutionCompleted, AgentStepStarted, AgentStepCompleted
from orkestra.core.tools import HostTool
from orkestra.workflows.runner import AgentRunner

# -------------------------------------------------------------------
# 1. Setup a Mock Tool
# -------------------------------------------------------------------
async def search_database(query: str, **kwargs) -> str:
    """Mock database search tool that takes 2 seconds to run."""
    await asyncio.sleep(2)
    return f"Database results for '{query}': Found 3 matching records."

search_tool = HostTool(
    name="search_database",
    description="Search the enterprise database.",
    func=search_database,
    schema={
        "type": "function",
        "function": {
            "name": "search_database",
            "description": "Search the enterprise database.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string"}},
                "required": ["query"]
            }
        }
    }
)

from orkestra.events.base import Event

# -------------------------------------------------------------------
# 2. Define a Global Event Listener
# -------------------------------------------------------------------
def on_any_event(event: Event):
    """
    By subscribing to the base 'Event' class, this single function acts
    as a wildcard firehose, capturing every single event in the framework!
    """
    # We can dynamically check the class name of the event
    event_name = event.__class__.__name__
    
    if event_name == "AgentStepStarted":
        print(f"\n[FRONTEND] 🤖 {event.agent_name} is thinking...")
    elif event_name == "ToolExecutionStarted":
        print(f"[FRONTEND] 🔄 Using tool '{event.tool_name}'...")
    elif event_name == "ToolExecutionCompleted":
        if event.error:
            print(f"[FRONTEND] ❌ Tool failed!")
        else:
            print(f"[FRONTEND] ✅ Tool finished.")
    elif event_name == "AgentStepCompleted" and event.response_content:
        print(f"\n[FRONTEND] 💬 {event.agent_name} says: {event.response_content}")

async def main():
    print("=== Orkestra: 06 Live Streaming Events ===\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    # 3. Create the EventBus and subscribe the wildcard handler
    event_bus = EventBus()
    event_bus.subscribe(Event, on_any_event)
    
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    agent = Agent(
        name="SupportBot",
        description="A bot that answers questions by searching the DB.",
        system_prompt="You are a helpful assistant. Use the search_database tool to answer the user's question.",
        provider=provider,
        tools=[search_tool],
        event_bus=event_bus # Pass the EventBus to the Agent!
    )
    
    runner = AgentRunner(agent=agent, event_bus=event_bus)
    
    user_prompt = "Can you look up the records for John Doe?"
    print(f"User: {user_prompt}\n")
    print("--- Simulating Live React Frontend ---")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    # Run the loop. The events will fire natively as it runs!
    await runner.arun()

if __name__ == "__main__":
    asyncio.run(main())
