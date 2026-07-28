import asyncio
import os
import json
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.tools import HostTool
from orkestra.workflows.runner import AgentRunner

# -------------------------------------------------------------------
# 1. Define Real-World DevOps Tools
# -------------------------------------------------------------------
async def check_server_status(hostname: str, **kwargs) -> str:
    """Simulates checking server health."""
    if hostname == "web-prod-1":
        return json.dumps({"status": "critical", "issue": "Nginx unresponsive", "cpu_usage": "98%"})
    return json.dumps({"status": "healthy", "cpu_usage": "45%"})

async def read_system_logs(hostname: str, lines: int, **kwargs) -> str:
    """Simulates reading recent error logs from a server."""
    if hostname == "web-prod-1":
        return "ERROR 14:02 - OutOfMemoryException in Nginx worker process\nERROR 14:03 - Connection refused"
    return "INFO: All systems nominal."

async def restart_service(hostname: str, service_name: str, **kwargs) -> str:
    """Simulates restarting a service on a remote host."""
    return f"SUCCESS: Service '{service_name}' on '{hostname}' has been gracefully restarted."

# -------------------------------------------------------------------
# 2. Wrap them in HostTools
# -------------------------------------------------------------------
check_server_tool = HostTool(
    name="check_server_status",
    description="Check the health status of a given server.",
    func=check_server_status,
    schema={
        "type": "function",
        "function": {
            "name": "check_server_status",
            "description": "Check the health status of a given server.",
            "parameters": {
                "type": "object",
                "properties": {"hostname": {"type": "string"}},
                "required": ["hostname"]
            }
        }
    }
)

read_logs_tool = HostTool(
    name="read_system_logs",
    description="Read the most recent error logs from a server.",
    func=read_system_logs,
    schema={
        "type": "function",
        "function": {
            "name": "read_system_logs",
            "description": "Read the most recent error logs from a server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hostname": {"type": "string"},
                    "lines": {"type": "integer"}
                },
                "required": ["hostname", "lines"]
            }
        }
    }
)

restart_service_tool = HostTool(
    name="restart_service",
    description="Restart a specific system service on a server.",
    func=restart_service,
    schema={
        "type": "function",
        "function": {
            "name": "restart_service",
            "description": "Restart a specific system service on a server.",
            "parameters": {
                "type": "object",
                "properties": {
                    "hostname": {"type": "string"},
                    "service_name": {"type": "string"}
                },
                "required": ["hostname", "service_name"]
            }
        }
    }
)

# -------------------------------------------------------------------
# 3. Main Workflow execution
# -------------------------------------------------------------------
async def main():
    print("=== Orkestra: 05 Multi-Tool DevOps Agent ===\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 4. Create an Agent with all 3 tools
    agent = Agent(
        name="DevOpsBot",
        description="A Level 3 SRE responsible for maintaining server uptime.",
        system_prompt=(
            "You are DevOpsBot, an elite Site Reliability Engineer. "
            "When a user reports a system issue, you should methodically investigate:\n"
            "1. Check the server status.\n"
            "2. Read the system logs to find the root cause.\n"
            "3. Take remediation action by restarting the affected service.\n"
            "Always explain to the user what you are doing at each step."
        ),
        provider=provider,
        tools=[check_server_tool, read_logs_tool, restart_service_tool]
    )
    
    runner = AgentRunner(agent=agent)
    
    user_prompt = "URGENT: Customers are reporting that the website is completely down! Please check web-prod-1 immediately!"
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    print("Running Agent loop... (Watch how the LLM chains tools together autonomously!)\n")
    await runner.arun()
    
    # Print the execution trace
    print("\n--- Execution History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            for tc in msg.tool_calls:
                print(f"🤖 DevOpsBot: [Uses Tool '{tc.function_name}' with args {tc.function_arguments}]")
        elif msg.role == "tool":
            print(f"🔧 System: {msg.content}")
        elif msg.role == "assistant":
            print(f"🤖 DevOpsBot: {msg.content}")
            
    print(f"\n[Token Usage: {agent.usage['prompt_tokens']} prompt, {agent.usage['completion_tokens']} completion]")

if __name__ == "__main__":
    asyncio.run(main())
