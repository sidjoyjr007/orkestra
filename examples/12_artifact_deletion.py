import asyncio
import os
import shutil
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.tools import HostTool
from orkestra.workflows.runner import AgentRunner

# 1. Fetch massive logs (same as Example 11)
async def fetch_massive_logs(**kwargs) -> str:
    header = "=== SYSTEM LOGS ===\n"
    boring_logs = "\n".join([f"INFO: [Timestamp {i}] System running nominally." for i in range(5000)])
    critical_error = "\nCRITICAL ERROR [Line 5001]: The server database crashed because out of memory!"
    return header + boring_logs + critical_error

fetch_logs_tool = HostTool(
    name="fetch_massive_logs",
    description="Fetches the full system logs.",
    func=fetch_massive_logs,
    max_result_length=300,
    schema={
        "type": "function",
        "function": {
            "name": "fetch_massive_logs",
            "description": "Fetches the full system logs.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
)

# 2. Simulate a background cron job wiping the /tmp folder
async def wipe_tmp_folder(**kwargs) -> str:
    """Simulates an OS cleanup script wiping the /tmp folder."""
    artifact_dir = "/tmp/orkestra_artifacts/deletion_demo"
    if os.path.exists(artifact_dir):
        shutil.rmtree(artifact_dir)
        return "CRON JOB COMPLETE: Wiped the /tmp folder successfully."
    return "CRON JOB COMPLETE: Nothing to wipe."

wipe_tmp_tool = HostTool(
    name="wipe_tmp_folder",
    description="Simulates an OS-level background cleanup of temporary files.",
    func=wipe_tmp_folder,
    schema={
        "type": "function",
        "function": {
            "name": "wipe_tmp_folder",
            "description": "Simulates an OS-level background cleanup.",
            "parameters": {"type": "object", "properties": {}}
        }
    }
)


async def main():
    print("=== Orkestra: 12 Artifact Deletion (Graceful Healing) ===")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    agent = Agent(
        name="DevOpsBot",
        description="A bot that analyzes logs.",
        system_prompt=(
            "You are a DevOps bot. Follow these exact steps:\n"
            "1. Call fetch_massive_logs.\n"
            "2. Call wipe_tmp_folder to simulate an OS cleanup event.\n"
            "3. Try to read the end of the logs to find the critical error.\n"
            "4. If the file is missing, autonomously call fetch_massive_logs again and then read it!"
        ),
        provider=provider,
        tools=[fetch_logs_tool, wipe_tmp_tool],
        session_id="deletion_demo",
        artifact_dir="/tmp/orkestra_artifacts/deletion_demo",
        max_iterations=15
    )
    
    runner = AgentRunner(agent=agent)
    
    user_prompt = "Execute your instructions."
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    await runner.arun()
    
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            print(f"🤖 DBAdminBot: [Attempts to call {msg.tool_calls[0].function_name}]")
        elif msg.role == "tool":
            snip = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
            print(f"🔧 System Result: {snip}")
        elif msg.role == "assistant" and msg.content:
            print(f"🤖 DBAdminBot: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
