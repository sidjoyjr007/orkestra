import asyncio
import os
import sys
import requests
import json
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.tools import HostTool
from orkestra.workflows.runner import AgentRunner

# 1. Define the real-world python function
async def get_weather_func(city: str, **kwargs) -> str:
    """Fetch weather using the free wttr.in API"""
    try:
        # We use format=j1 to get clean JSON data
        url = f"https://wttr.in/{city}?format=j1"
        response = requests.get(url, timeout=10)
        data = response.json()
        current = data["current_condition"][0]
        
        return json.dumps({
            "temp_C": current["temp_C"],
            "temp_F": current["temp_F"],
            "description": current["weatherDesc"][0]["value"]
        })
    except Exception as e:
        return f"Error fetching weather: {e}"

# 2. Wrap it in a HostTool so the LLM understands it
get_weather_tool = HostTool(
    name="get_weather",
    description="Get the current weather for a specific city.",
    func=get_weather_func,
    schema={
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get the current weather for a specific city.",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "The name of the city, e.g. London or Tokyo"}
                },
                "required": ["city"]
            }
        }
    }
)

async def main():
    print("=== Orkestra: 02 Tool Agent ===\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 3. Create the Agent and give it the tool
    agent = Agent(
        name="WeatherBot",
        description="A helpful assistant that checks the weather.",
        system_prompt="You are a helpful meteorologist. Always use the get_weather tool to answer questions.",
        provider=provider,
        tools=[get_weather_tool]
    )
    
    # 4. Use AgentRunner
    runner = AgentRunner(agent=agent)
    
    city = sys.argv[1] if len(sys.argv) > 1 else "Tokyo"
    print(f"User: What is the weather like in {city} right now?\n")
    await agent.aadd_message(Message(role="user", content=f"What is the weather like in {city} right now?"))
    
    print("Running Agent loop...\n")
    await runner.arun()
    
    # Print the final conversation history
    print("--- Execution History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            print(f"🤖 WeatherBot: [Calls Tool '{msg.tool_calls[0].function_name}' with args {msg.tool_calls[0].function_arguments}]")
        elif msg.role == "tool":
            print(f"🔧 Tool Result: {msg.content}")
        elif msg.role == "assistant":
            print(f"🤖 WeatherBot: {msg.content}")
            
    print(f"\n[Token Usage: {agent.usage['prompt_tokens']} prompt, {agent.usage['completion_tokens']} completion]")

if __name__ == "__main__":
    asyncio.run(main())
