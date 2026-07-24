import asyncio
import os
import logging
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.memory.in_memory import InMemoryStore
from orkestra.workspace.in_memory import InMemoryWorkspaceStore

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    workspace = InMemoryWorkspaceStore()
    memory = InMemoryStore()
    
    agent = Agent(
        name="PlannerBot",
        description="A bot that plans and executes complex tasks.",
        system_prompt="You are an autonomous planner. Break down the user's request into a plan using the create_plan tool. Once created, execute each task step-by-step, using the update_task tool to mark your progress. Do not proceed until you have successfully planned and executed the request.",
        provider=provider,
        memory=memory,
        session_id="planning_session_1",
        workspace=workspace,
        max_iterations=8
    )
    
    print("🤖 Agent Initialized with Workspace Planning")
    print("-------------------------------------------------------------------")
    
    await agent.aadd_message(Message(role="user", content="I need you to write a poem about the ocean, and then translate it into French."))
    
    runner = AgentRunner(agent)
    await runner.arun()
    
    print("\n-------------------------------------------------------------------")
    print("Conversation Complete. Let's see the workspace history:")
    print("-------------------------------------------------------------------")
    
    # Show the plans that were created and archived
    all_plans = workspace.plans.get("planning_session_1", [])
    for idx, plan in enumerate(all_plans):
        print(f"Plan {idx+1} [Status: {plan.status}]:")
        for task in plan.tasks:
            print(f"  - [{task.status}] Task {task.id}: {task.description} (Notes: {task.notes})")

if __name__ == "__main__":
    asyncio.run(main())
