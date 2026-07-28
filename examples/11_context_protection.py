import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.tools import HostTool
from orkestra.workflows.runner import AgentRunner

# 1. Create a tool that returns a MASSIVE string (e.g. 50,000 characters)
async def fetch_massive_logs(**kwargs) -> str:
    """Returns a massive system log file."""
    header = "=== SYSTEM LOGS ===\n"
    # Create 5,000 lines of boring logs
    boring_logs = "\n".join([f"INFO: [Timestamp {i}] System running nominally." for i in range(5000)])
    
    # Hide the critical error at the very bottom!
    critical_error = "\nCRITICAL ERROR [Line 5001]: The server database crashed because out of memory!"
    
    return header + boring_logs + critical_error

# 2. Register the tool with a strict max_result_length!
fetch_logs_tool = HostTool(
    name="fetch_massive_logs",
    description="Fetches the full system logs. Warning: Output may be extremely large.",
    func=fetch_massive_logs,
    max_result_length=300, # Orkestra will truncate anything over 300 characters!
    schema={
        "type": "function",
        "function": {
            "name": "fetch_massive_logs",
            "description": "Fetches the full system logs.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
)

async def main():
    print("=== Orkestra: 11 Context Protection (Tool Truncation) ===")
    print("This example demonstrates how Orkestra protects the LLM context window")
    print("when a tool returns a massive payload, and how it dynamically injects")
    print("a chunk-reader tool so the LLM can paginate the rest!\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    agent = Agent(
        name="DevOpsBot",
        description="A bot that analyzes logs.",
        system_prompt="You are a DevOps bot. Fetch the logs and find the exact CRITICAL ERROR at the end.",
        provider=provider,
        tools=[fetch_logs_tool],
        session_id="session_truncation_demo",
        max_iterations=15,
        artifact_dir="/tmp/my_k8s_pvc_volume" # Explicitly defining a shared volume path!
    )
    
    runner = AgentRunner(agent=agent)
    
    user_prompt = "Fetch the logs and tell me what the critical error is."
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    # Run the loop!
    await runner.arun()
    
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            print(f"🤖 DBAdminBot: [Attempts to call {msg.tool_calls[0].function_name}]")
        elif msg.role == "tool":
            # Print only the first 100 chars to not flood the console
            snip = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            print(f"🔧 System Result: {snip}")
            if "[TRUNCATED]" in msg.content:
                print("   ⚠️ (ORKESTRA TRUNCATED THE REST AND SAVED IT TO DISK!)")
        elif msg.role == "assistant":
            print(f"🤖 DBAdminBot: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
