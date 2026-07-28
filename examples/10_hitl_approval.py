import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.tools import HostTool
from orkestra.workflows.runner import AgentRunner
from orkestra.events.bus import EventBus
from orkestra.events.base import HumanApprovalRequested, HumanApprovalProvided

# 1. Create a dangerous tool
async def drop_database(db_name: str, **kwargs) -> str:
    """Drops a database. Very dangerous!"""
    return f"SUCCESS: Database '{db_name}' has been permanently deleted."

drop_db_tool = HostTool(
    name="drop_database",
    description="Deletes a production database.",
    func=drop_database,
    requires_approval=True, # THIS TELLS ORKESTRA TO PAUSE!
    schema={
        "type": "function",
        "function": {
            "name": "drop_database",
            "description": "Deletes a production database.",
            "parameters": {
                "type": "object",
                "properties": {"db_name": {"type": "string"}},
                "required": ["db_name"]
            }
        }
    }
)

async def main():
    print("=== Orkestra: 10 Human-in-the-Loop (HITL) ===")
    print("This example shows how Orkestra uses native Python asyncio.Future")
    print("to pause execution in the middle of a loop and wait for human approval.\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    event_bus = EventBus()
    
    # 2. Subscribe to the HumanApprovalRequested event
    async def on_approval_requested(event: HumanApprovalRequested):
        print(f"\n⚠️ WARNING: The Agent wants to call '{event.tool_name}' with args: {event.tool_args}")
        print("Waiting 3 seconds to simulate human reviewing the request...")
        await asyncio.sleep(3)
        
        # We simulate the human saying NO
        print("👨‍💻 HUMAN DECISION: REJECTED")
        
        # 3. Publish the decision back to the EventBus!
        # Orkestra's executor is listening for this event and will instantly unpause.
        await event_bus.apublish(HumanApprovalProvided(
            tool_call_id=event.tool_call_id,
            result="[HUMAN REJECTED] You do not have permission to drop the database."
        ))

    event_bus.subscribe(HumanApprovalRequested, on_approval_requested)
    
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    agent = Agent(
        name="DBAdminBot",
        description="A database administrator.",
        system_prompt="You are a helpful database admin.",
        provider=provider,
        tools=[drop_db_tool],
        event_bus=event_bus
    )
    
    runner = AgentRunner(agent=agent, event_bus=event_bus)
    
    user_prompt = "Can you please drop the 'production_users' database?"
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    # Watch how it natively pauses and resumes!
    await runner.arun()
    
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            print(f"🤖 DBAdminBot: [Attempts to call {msg.tool_calls[0].function_name}]")
        elif msg.role == "tool":
            print(f"🔧 System Result: {msg.content}")
        elif msg.role == "assistant":
            print(f"🤖 DBAdminBot: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
