import asyncio
import os
import logging
import json
import chromadb
import uuid

from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.core.tools import Tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 1. Pre-embed tools into ChromaDB (Mocking the external system)
def setup_mock_vectordb(agent_id: str):
    print("📦 Pre-embedding tools into ChromaDB (localhost:8100)...")
    try:
        client = chromadb.HttpClient(host="localhost", port=8100)
    except Exception as e:
        print(f"Failed to connect to Chroma. Make sure your docker container is running on 8100: {e}")
        return False
        
    collection = client.get_or_create_collection(name="orkestra_tools")
    
    # We create 3 distinct executable tools
    tools_data = [
        {
            "id": "tool_weather",
            "text": "Get the current weather for a city.",
            "metadata": {
                "agent_id": agent_id,
                "type": "local",
                "schema": json.dumps({
                    "type": "function",
                    "function": {
                        "name": "get_weather",
                        "description": "Get the current weather for a city.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "city": {"type": "string"}
                            },
                            "required": ["city"]
                        }
                    }
                })
            }
        },
        {
            "id": "tool_time",
            "text": "Get the current time in a timezone.",
            "metadata": {
                "agent_id": agent_id,
                "type": "local",
                "schema": json.dumps({
                    "type": "function",
                    "function": {
                        "name": "get_current_time",
                        "description": "Get the current time in a timezone.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "timezone": {"type": "string"}
                            },
                            "required": ["timezone"]
                        }
                    }
                })
            }
        },
        {
            "id": "tool_mcp_search",
            "text": "Search the web using DuckDuckGo.",
            "metadata": {
                "agent_id": agent_id,
                "type": "mcp", # This one is an MCP tool!
                "mcp_url": "http://localhost:8020/mcp",
                "schema": json.dumps({
                    "type": "function",
                    "function": {
                        "name": "web-search",
                        "description": "Search the web using DuckDuckGo.",
                        "parameters": {
                            "type": "object",
                            "properties": {
                                "query": {"type": "string"}
                            },
                            "required": ["query"]
                        }
                    }
                })
            }
        }
    ]
    
    # Upsert into Chroma
    collection.upsert(
        ids=[t["id"] for t in tools_data],
        documents=[t["text"] for t in tools_data],
        metadatas=[t["metadata"] for t in tools_data]
    )
    print("✅ Pre-embedding complete.")
    return True

async def run_tool_rag():
    agent_id = str(uuid.uuid4())
    if not setup_mock_vectordb(agent_id):
        return
        
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    base_provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # WRAP THE PROVIDER TO DEMONSTRATE WHAT IS SENT TO THE LLM!
    class InterceptingProvider:
        def __init__(self, provider):
            self.provider = provider
            self.event_bus = getattr(provider, "event_bus", None)
            
        def get_messages(self):
            return self.provider.get_messages()
            
        async def agenerate(self, messages, **kwargs):
            system_prompt = kwargs.get('system_prompt', None)
            tools = kwargs.get('tools', None)
            print("\n" + "="*50)
            print("🚀 RAW PAYLOAD SENT TO LLM PROVIDER 🚀")
            print("="*50)
            print("System Prompt:")
            print(f"  {system_prompt}")
            print("\nMessages:")
            for m in messages:
                print(f"  [{m.role.upper()}]: {m.content}")
            print("\nTools (Schemas injected into LLM context):")
            if not tools:
                print("  None")
            else:
                for t in tools:
                    name = t.get('function', {}).get('name', 'Unknown')
                    desc = t.get('function', {}).get('description', 'No description')
                    print(f"  - Tool Name: {name}")
                    print(f"  - Description: {desc}")
            print("="*50 + "\n")
            return await self.provider.agenerate(messages, **kwargs)
            
    provider = InterceptingProvider(base_provider)
    
    print("\n🤖 Initializing Agent with ZERO loaded tools (Tool RAG mode)")
    agent = Agent(
        name="RouterBot",
        description="I dynamically load tools from ChromaDB.",
        system_prompt="You are a smart assistant. Use the tools provided to you to answer the user.",
        provider=provider,
        id=agent_id,
        tool_registry_url="http://localhost:8100" # Activates RAG!
    )
    
    # Initially, it only has `search_tools` builtin.
    print(f"Current Tools: {[t.name for t in agent.tools]}")
    
    runner = AgentRunner(agent)
    
    print("\n🗣️ User: Search the web for the latest news on Apple.")
    # When this runs, the AgentRunner will semantically match "Search the web"
    # and automatically inject the "web-search" MCP tool BEFORE passing it to Gemini!
    
    # Temporarily lower the threshold for the demo to guarantee a match
    agent.tool_registry.search = lambda q: agent.tool_registry.__class__.search(agent.tool_registry, q, threshold=0.1)
    
    await agent.aadd_message(Message(role="user", content="Search the web for the latest news on Apple."))
    
    print("🤖 Agent is thinking...")
    response = await runner.arun()
    
    print(f"\n✅ Tools that were dynamically loaded for this turn: {[t.name for t in agent.tools]}")
    print(f"✅ Final Response:\n{response.message.content}")

if __name__ == "__main__":
    asyncio.run(run_tool_rag())
