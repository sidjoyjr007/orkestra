import asyncio
import os
import json
import chromadb
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.workflows.runner import AgentRunner
from orkestra.workspace.in_memory import InMemoryWorkspaceStore
from orkestra.core.tool_registry import ToolRegistry
from orkestra.core.tools import HostTool

# --- Mock Tool for Schema Generation ---
k8s_tool = HostTool(
    name="deploy_kubernetes",
    description="Deploys a Kubernetes cluster to the cloud.",
    func=lambda: "",
    schema={
        "type": "function",
        "function": {
            "name": "deploy_kubernetes",
            "description": "Deploys a Kubernetes cluster.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
)

# --- Monkey-patch ToolRegistry to use an In-Memory DB for this demo ---
_original_init = ToolRegistry.__init__
def mock_init(self, url, agent_id, collection_name="orkestra_tools"):
    self.url = url
    self.agent_id = agent_id
    self.client = chromadb.Client() # In-Memory DB
    self.collection = self.client.get_or_create_collection(name=collection_name)
ToolRegistry.__init__ = mock_init

async def main():
    print("=== Orkestra: 17 Tool RAG + Persistent Planning ===")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    session_id = "session_rag_workspace"
    agent_id = "devops_agent_99"
    
    # 1. Initialize our databases
    workspace = InMemoryWorkspaceStore()
    registry = ToolRegistry(url="http://localhost:8000", agent_id=agent_id)
    
    # 2. Seed our Vector Database with a raw Python tool
    deploy_k8s_code = """
async def deploy_kubernetes(**kwargs) -> str:
    return "Kubernetes cluster deployed successfully to AWS EKS! (DYNAMICALLY COMPILED)"
"""
    registry.collection.add(
        ids=["tool_1"],
        documents=["devops cloud deploy infrastructure kubernetes cluster aws eks"],
        metadatas=[
            {"type": "host_tool", "agent_id": agent_id, "schema": json.dumps(k8s_tool.schema), "code": deploy_k8s_code}
        ]
    )
    print("✅ Seeded Vector Database with tools.")
    
    # 3. Create the agent. 
    # Notice how we pass `workspace` and `tool_registry_url`. 
    # We pass ZERO manual tools. The framework will AUTO-INJECT the planning tools!
    agent = Agent(
        name="EnterpriseOpsBot",
        description="A bot that strictly follows a plan and pulls tools just-in-time.",
        system_prompt=(
            "You are an extremely disciplined AI DevOps planner. YOU ARE ABSOLUTELY FORBIDDEN FROM EXECUTING ANY BUSINESS LOGIC OR SEARCH TOOLS UNTIL YOU HAVE CREATED A PLAN.\n\n"
            "Rule 1: Your very first action MUST ALWAYS be to call 'create_plan' with the steps to fulfill the user's request.\n"
            "Rule 2: If you use any other tool before 'create_plan', you will fail your mission.\n"
            "Rule 3: After creating a plan, if you need a tool you don't have, use 'search_tools' to query the Vector DB for it.\n"
            "Rule 4: Use 'update_task' to mark tasks as IN_PROGRESS, and then DONE as you finish them."
        ),
        provider=provider,
        id=agent_id,
        session_id=session_id,
        workspace=workspace,
        tool_registry_url="http://localhost:8000",
        max_iterations=8 # Give it enough iterations to search for tools and update the plan
    )
    
    runner = AgentRunner(agent=agent)
    
    user_prompt = "Can you help me setup my new scalable backend? I need you to deploy a kubernetes cluster."
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    await runner.arun()
    
    print("\n--- Active Plan State ---")
    active_plan = await workspace.aget_active_plan(session_id)
    if active_plan:
        print(active_plan.to_markdown())
    else:
        print("No active plan (it was likely auto-archived upon completion!).")
        
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            calls = ", ".join([t.function_name for t in msg.tool_calls])
            print(f"🤖 EnterpriseOpsBot: [Calling Tools: {calls}]")
        elif msg.role == "assistant" and msg.content:
            print(f"🤖 EnterpriseOpsBot: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
