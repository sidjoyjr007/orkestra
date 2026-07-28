import asyncio
import os
import json
import chromadb
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.workflows.runner import AgentRunner
from orkestra.core.tool_registry import ToolRegistry
from orkestra.core.tools import HostTool

# --- 1. Let's create some tools we want to store in our Vector Database ---

async def calculate_mortgage(**kwargs) -> str:
    """Calculates a mortgage."""
    return "Your estimated monthly mortgage payment is $2,450."

mortgage_tool = HostTool(
    name="calculate_mortgage",
    description="Calculates a mortgage based on interest rate and principal.",
    func=calculate_mortgage,
    schema={
        "type": "function",
        "function": {
            "name": "calculate_mortgage",
            "description": "Calculates a mortgage.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
)

async def deploy_kubernetes(**kwargs) -> str:
    """Deploys a Kubernetes cluster."""
    return "Kubernetes cluster deployed successfully to AWS EKS!"

k8s_tool = HostTool(
    name="deploy_kubernetes",
    description="Deploys a Kubernetes cluster to the cloud.",
    func=deploy_kubernetes,
    schema={
        "type": "function",
        "function": {
            "name": "deploy_kubernetes",
            "description": "Deploys a Kubernetes cluster.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
)

# --- 2. Monkey-patch ToolRegistry to use an In-Memory DB for this demo ---
# In production, Orkestra uses chromadb.HttpClient to connect to your Docker container!
_original_init = ToolRegistry.__init__
def mock_init(self, url, agent_id, collection_name="orkestra_tools"):
    self.url = url
    self.agent_id = agent_id
    self.client = chromadb.Client() # In-Memory DB
    self.collection = self.client.get_or_create_collection(name=collection_name)
ToolRegistry.__init__ = mock_init


async def main():
    print("=== Orkestra: 15 Just-In-Time Tool Selection (Tool RAG) ===")
    print("This example demonstrates how an Agent starts with ZERO tools,")
    print("but dynamically pulls the exact tools it needs from a Vector DB!\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    agent_id = "agent_123"
    
    # 3. Seed our Vector Database with our tools!
    # In production, an external cron job or pipeline usually handles this embedding process.
    registry = ToolRegistry(url="http://localhost:8000", agent_id=agent_id)
    
    # We will pass the raw Python source code for the tool into the database!
    deploy_k8s_code = """
async def deploy_kubernetes(**kwargs) -> str:
    # This code will be dynamically compiled and executed by Orkestra!
    return "Kubernetes cluster deployed successfully to AWS EKS! (DYNAMICALLY COMPILED)"
"""
    
    registry.collection.add(
        ids=["tool_1", "tool_2"],
        documents=["financial math mortgage calculator loan interest", "devops cloud deploy infrastructure kubernetes cluster"],
        metadatas=[
            {"type": "tool", "agent_id": agent_id, "schema": json.dumps(mortgage_tool.schema)},
            {"type": "host_tool", "agent_id": agent_id, "schema": json.dumps(k8s_tool.schema), "code": deploy_k8s_code}
        ]
    )
    print("✅ Seeded Vector Database with 2 complex tools.")
    
    # 4. Initialize the Agent with ZERO TOOLS
    agent = Agent(
        name="DynamicBot",
        description="A bot that pulls tools just-in-time.",
        system_prompt="You are a helpful assistant. State your plan first starting with 'Plan:'. Then use the tools.",
        provider=provider,
        id=agent_id,
        tools=[], # EMPTY TOOLBELT!
        tool_registry_url="http://localhost:8000" # Tell the Agent where the DB is!
    )
    
    runner = AgentRunner(agent=agent)
    
    # 5. Let's ask it a DevOps question. It should pull the Kubernetes tool!
    user_prompt = "I need to deploy a new scalable backend. Can you deploy a cluster for me?"
    print(f"\nUser: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    await runner.arun()
    
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            print(f"🤖 DynamicBot: [Calling Tool '{msg.tool_calls[0].function_name}']")
        elif msg.role == "tool":
            print(f"🔧 System Result: {msg.content}")
        elif msg.role == "assistant" and msg.content:
            print(f"🤖 DynamicBot: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
