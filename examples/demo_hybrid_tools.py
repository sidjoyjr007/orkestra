import asyncio
import os
import logging
from datetime import datetime

from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.mcp.http_client import MCPHttpToolkit
from orkestra.core.tools import Tool

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# 1. Define a Custom Local Tool
def get_current_time(timezone: str = "UTC") -> str:
    """Returns the current date and time."""
    from datetime import datetime
    import pytz
    
    try:
        tz = pytz.timezone(timezone)
        now = datetime.now(tz)
        return now.strftime("%Y-%m-%d %H:%M:%S %Z")
    except Exception as e:
        return f"Error: {str(e)}"

time_tool = Tool(
    name="get_current_time",
    description="Get the current time in a specific timezone.",
    func=get_current_time,
    schema={
        "type": "function",
        "function": {
            "name": "get_current_time",
            "description": "Get the current time in a specific timezone.",
            "parameters": {
                "type": "object",
                "properties": {
                    "timezone": {
                        "type": "string",
                        "description": "The timezone name (e.g., 'America/New_York', 'UTC', 'Asia/Tokyo')."
                    }
                },
                "required": ["timezone"]
            }
        }
    },
    dependencies=["pytz"] # Orkestra will auto-install this in the Docker sandbox!
)

async def run_hybrid_agent():
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 2. Fetch Remote Tools via MCP
    print("🔌 Connecting to Local DuckDuckGo MCP Server on port 8020...")
    mcp_client = MCPHttpToolkit("http://localhost:8020/mcp")
    mcp_tools = await mcp_client.load_tools()
    
    # 3. Combine Local + Remote Tools
    all_tools = [time_tool] + mcp_tools
    print(f"✅ Loaded {len(all_tools)} tools ({len(mcp_tools)} remote, 1 local). Injecting into Agent...")
    
    # 4. Initialize Agent
    agent = Agent(
        name="HybridBot",
        description="I have access to both local Python functions and remote MCP servers.",
        system_prompt="You have access to a local time tool and a remote DuckDuckGo search tool via MCP. Use them together to answer the user's questions.",
        provider=provider,
        tools=all_tools
    )
    
    runner = AgentRunner(agent)
    
    print("\n🗣️ User: What time is it in Tokyo right now, and what is the current weather there?")
    await agent.aadd_message(Message(role="user", content="What time is it in Tokyo right now? Then use DuckDuckGo to search for the current weather there."))
    
    print("🤖 Agent is thinking and executing hybrid tools...")
    response = await runner.arun()
    
    print(f"\n✅ Final Response:\n{response.message.content}")
    
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(run_hybrid_agent())
