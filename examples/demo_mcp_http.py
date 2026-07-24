import asyncio
import os
import logging

from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.mcp.http_client import MCPHttpToolkit

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def real_mcp_environment():
    # 1. Initialize Orkestra Provider
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    # 2. Connect to the Live MCP HTTP Server
    print("🔌 Connecting to Local DuckDuckGo MCP Server on port 8020...")
    mcp_client = MCPHttpToolkit("http://localhost:8020/mcp")
    mcp_tools = await mcp_client.load_tools()
        
    # Pass the mapped tools directly into the Agent!
    print(f"✅ Loaded {len(mcp_tools)} tools from remote server. Injecting into Agent...")
    agent = Agent(
        name="MCPBot",
        description="I can use remote tools via MCP.",
        system_prompt="You have access to a DuckDuckGo search tool via an MCP server. Use it to answer the user's questions accurately.",
        provider=provider,
        tools=mcp_tools
    )
    
    runner = AgentRunner(agent)
    
    print("\n🗣️ User: What is the current stock price of Apple?")
    await agent.aadd_message(Message(role="user", content="Please use DuckDuckGo to search for the current stock price of Apple (AAPL)."))
    
    print("🤖 Agent is thinking and executing remote tools...")
    response = await runner.arun()
    
    print(f"\n✅ Final Response:\n{response.message.content}")
    
    # 3. Clean up the MCP client
    await mcp_client.close()

if __name__ == "__main__":
    asyncio.run(real_mcp_environment())
