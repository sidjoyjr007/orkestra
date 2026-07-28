import asyncio
import os
import json
import httpx
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.workflows.runner import AgentRunner
from orkestra.mcp.http_client import MCPHttpToolkit

# --- Mocking the HTTPX Client to simulate a real MCP Server ---
class MockStream:
    def __init__(self, data):
        self.data = data
        self.status_code = 200
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        pass
        
    async def aiter_lines(self):
        yield f"data: {json.dumps(self.data)}"

class MockMCPClient(httpx.AsyncClient):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
    def stream(self, method, url, **kwargs):
        req = kwargs.get("json", {})
        
        # 1. Simulate tools/list endpoint
        if req.get("method") == "tools/list":
            return MockStream({
                "result": {
                    "tools": [
                        {
                            "name": "get_weather",
                            "description": "Get the weather for a location from the remote MCP server.",
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "location": {"type": "string", "description": "City name"}
                                },
                                "required": ["location"]
                            }
                        }
                    ]
                }
            })
            
        # 2. Simulate tools/call endpoint
        elif req.get("method") == "tools/call":
            args = req.get("params", {}).get("arguments", {})
            location = args.get("location", "Unknown")
            return MockStream({
                "result": {
                    "isError": False,
                    "content": [{"type": "text", "text": f"The weather in {location} is 72°F and sunny!"}]
                }
            })
            
        raise RuntimeError("Unknown mock endpoint")

# Monkey-patch the MCPHttpToolkit to use our mock client
# In production, you would NOT do this. It would connect to a real server.
_original_init = MCPHttpToolkit.__init__
def mock_init(self, url, headers=None):
    _original_init(self, url, headers)
    self._client = MockMCPClient(timeout=30.0)
MCPHttpToolkit.__init__ = mock_init


async def main():
    print("=== Orkestra: 14 Model Context Protocol (MCP) ===")
    print("This example connects to an external MCP Server (simulated here)")
    print("and dynamically loads its tools for the agent to use over the internet!\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 1. Connect to the MCP Server
    mcp = MCPHttpToolkit(url="https://api.my-mcp-server.com/sse")
    
    # 2. Dynamically load all tools from the remote server
    print("Fetching tools from remote MCP Server...")
    mcp_tools = await mcp.load_tools()
    print(f"Loaded {len(mcp_tools)} tools from MCP Server!\n")
    
    # 3. Pass the remote tools natively to the Orkestra Agent
    agent = Agent(
        name="WeatherBot",
        description="A bot that uses external MCP tools.",
        system_prompt="You are a helpful assistant. Use the tools provided to you.",
        provider=provider,
        tools=mcp_tools, # Inject the MCP tools!
    )
    
    runner = AgentRunner(agent=agent)
    
    user_prompt = "What is the weather like in San Francisco?"
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    await runner.arun()
    
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            print(f"🤖 WeatherBot: [Calling remote MCP Tool '{msg.tool_calls[0].function_name}']")
        elif msg.role == "tool":
            print(f"🌐 MCP Server Response: {msg.content}")
        elif msg.role == "assistant" and msg.content:
            print(f"🤖 WeatherBot: {msg.content}")
            
    await mcp.close()

if __name__ == "__main__":
    asyncio.run(main())
