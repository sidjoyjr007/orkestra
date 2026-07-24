import asyncio
import os
import json
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.core.messages import Message
from orkestra.core.tools import Tool
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.memory.in_memory import InMemoryStore
from orkestra.mcp.http_client import MCPTool
from orkestra.core.state import AgentStateSerializer
import httpx

# Shared in-memory store representing our "Database"
db = InMemoryStore()

def dummy_native_tool(arg1: str):
    return f"Native tool executed with {arg1}"

base_tools = [
    Tool(name="dummy_native", description="A native tool", func=dummy_native_tool, schema={"type": "function", "function": {"name": "dummy_native"}})
]

async def run_demo():
    print("=== Agent Serialization & Resume Demo ===")
    
    api_key = os.getenv("GEMINI_API_KEY", "dummy")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    session_id = "test_session_123"
    
    # 1. Initialize Agent
    print("\n[1] Initializing Agent...")
    agent1 = Agent(
        name="ResumeBot",
        description="I am testing serialization.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        tools=base_tools.copy(),
        memory=db,
        session_id=session_id
    )
    
    # Simulate dynamically loading an MCP Tool (e.g. from Tool RAG)
    print("[2] Dynamically injecting a remote MCP Tool into the agent...")
    mcp_schema = {"type": "function", "function": {"name": "remote_search", "description": "Search the web"}}
    mcp_tool = MCPTool(name="remote_search", description="Search the web", schema=mcp_schema, url="http://localhost:8020/mcp", headers={}, client=httpx.AsyncClient())
    agent1.tools.append(mcp_tool)
    
    # Add a message and save checkpoint manually (simulating the end of a turn)
    await agent1.aadd_message(Message(role="user", content="Hello!"))
    await db.asave_checkpoint(session_id, AgentStateSerializer.to_dict(agent1))
    
    print("\n[3] 💥 CRASH! The server died. agent1 is destroyed.")
    del agent1
    
    # 4. Resume Agent
    print("\n[4] Restarting server and initializing a new Agent with the same session_id...")
    agent2 = Agent(
        name="NewBot", # Note: these args will be overwritten by the checkpoint
        description="...",
        system_prompt="...",
        provider=provider,
        tools=base_tools.copy(), # We provide the raw python base tools
        memory=db,
        session_id=session_id
    )
    
    # Load state manually (normally you'd put this in __init__, but we'll do it explicitly for the demo)
    checkpoint = await db.aload_checkpoint(session_id)
    if checkpoint:
        AgentStateSerializer.load_state(agent2, checkpoint, base_tools)
        print("✅ Checkpoint Loaded!")
    
    # Verify state
    print(f"\n[5] Verifying Restored State:")
    print(f"Name: {agent2.name}")
    print(f"Session ID: {agent2.session_id}")
    print(f"Number of loaded tools: {len(agent2.tools)}")
    
    for t in agent2.tools:
        if isinstance(t, MCPTool):
            print(f"- Tool '{t.name}': Reconstructed live MCP Client to {t._url}!")
        else:
            print(f"- Tool '{t.name}': Reattached to native Python function '{t.func.__name__}'!")
            
    print(f"\nMessage History: {[m.content for m in agent2.messages]}")

if __name__ == "__main__":
    asyncio.run(run_demo())
