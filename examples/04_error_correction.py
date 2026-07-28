import asyncio
import os
import re
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.tools import HostTool
from orkestra.workflows.runner import AgentRunner

# 1. A tool that is very strict and raises exceptions!
async def get_sales_data(date: str, **kwargs) -> str:
    """Gets sales data for a specific date."""
    
    # We strictly enforce YYYY-MM-DD format
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", date):
        # Raising an exception will NOT crash the script! 
        # Orkestra will catch it and feed it back to the agent so it can learn and retry.
        raise ValueError(f"CRITICAL ERROR: Date must be in exact YYYY-MM-DD format! You provided: '{date}'")
        
    return f"Sales for {date}: $15,420.00"

strict_sales_tool = HostTool(
    name="get_sales_data",
    description="Get sales data for a given date.",
    func=get_sales_data,
    schema={
        "type": "function",
        "function": {
            "name": "get_sales_data",
            "description": "Get sales data for a given date.",
            "parameters": {
                "type": "object",
                "properties": {
                    "date": {"type": "string", "description": "The date to check."}
                },
                "required": ["date"]
            }
        }
    }
)

async def main():
    print("=== Orkestra: 04 Error Correction ===\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    agent = Agent(
        name="SalesBot",
        description="A helpful sales assistant.",
        system_prompt="You are SalesBot. Always use the get_sales_data tool to answer questions. IMPORTANT: ALWAYS format dates as 'MM-DD-YYYY' when calling tools.",
        provider=provider,
        tools=[strict_sales_tool]
    )
    
    runner = AgentRunner(agent=agent)
    
    # Notice we give it an ambiguous date to trick the LLM into failing the regex!
    user_prompt = "How much money did we make on January 5th 2024?"
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    print("Running Agent loop...\n")
    await runner.arun()
    
    # Print the final conversation history
    print("--- Execution History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            print(f"🤖 SalesBot: [Calls Tool '{msg.tool_calls[0].function_name}' with args {msg.tool_calls[0].function_arguments}]")
        elif msg.role == "tool":
            # Orkestra natively prefixes all caught python exceptions with "Error executing"
            if msg.content.startswith("Error executing"):
                print(f"❌ Tool Crashed (Caught by Orkestra): {msg.content}")
            else:
                print(f"✅ Tool Succeeded: {msg.content}")
        elif msg.role == "assistant":
            print(f"🤖 SalesBot: {msg.content}")
            
    print(f"\n[Token Usage: {agent.usage['prompt_tokens']} prompt, {agent.usage['completion_tokens']} completion]")

if __name__ == "__main__":
    asyncio.run(main())
