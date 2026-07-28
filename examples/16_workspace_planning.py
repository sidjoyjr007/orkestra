import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.workflows.runner import AgentRunner
from orkestra.workspace.in_memory import InMemoryWorkspaceStore
from orkestra.workspace.tools import get_planning_tools
from orkestra.core.tools import HostTool

# Mock tool to simulate completing real work
async def setup_database(**kwargs) -> str:
    return "Database has been successfully set up and migrated!"

setup_db_tool = HostTool(
    name="setup_database",
    description="Sets up the database for the project.",
    func=setup_database,
    schema={
        "type": "function",
        "function": {
            "name": "setup_database",
            "description": "Sets up the database.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
)

async def main():
    print("=== Orkestra: 16 Workspace & Persistent Planning ===")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    session_id = "session_123"
    
    # 2. Initialize the Workspace Store (In-Memory for demo, Postgres for production)
    workspace = InMemoryWorkspaceStore()
    
    # 3. Create the agent with actual tools (Planning tools are AUTO-INJECTED!)
    agent = Agent(
        name="PlannerBot",
        description="A bot that strictly follows a plan.",
        system_prompt=(
            "You are a meticulous AI planner. When given a complex request, you MUST:\n"
            "1. Use 'create_plan' to break it down into steps.\n"
            "2. Complete the tasks one by one.\n"
            "3. Use 'update_task' to mark tasks as IN_PROGRESS, and then DONE as you finish them."
        ),
        provider=provider,
        id="planner_agent",
        workspace=workspace,
        tools=[setup_db_tool] # No need to manually inject planning tools!
    )
    
    runner = AgentRunner(agent=agent)
    
    user_prompt = "Can you help me setup my new project? I need you to setup the database."
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    await runner.arun()
    
    print("\n--- Active Plan State ---")
    # Let's peek into the workspace database to see the final plan state!
    active_plan = await workspace.aget_active_plan(session_id)
    if active_plan:
        print(active_plan.to_markdown())
    else:
        print("No active plan (it was likely auto-archived upon completion!).")
        
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            calls = ", ".join([t.function_name for t in msg.tool_calls])
            print(f"🤖 PlannerBot: [Calling Tools: {calls}]")
        elif msg.role == "assistant" and msg.content:
            print(f"🤖 PlannerBot: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
