import asyncio
import os
import logging
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.core.tools import Tool
from orkestra.memory.in_memory import InMemoryStore
from orkestra.core.context import KeepAllStrategy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("TruncationDemo")

def fetch_huge_logs(server_name: str) -> str:
    """Fetch server logs. Returns a massive string."""
    print(f"\n[Tool Execution] Fetching huge logs for {server_name}...")
    # Generate 5,000 characters of fake logs
    logs = "START OF LOGS\n"
    for i in range(100):
        logs += f"[{i}] WARN: Memory usage high on {server_name}. Please investigate memory leak in module X.\n"
    logs += "END OF LOGS\n"
    return logs

async def main():
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # Notice we set max_result_length=200!
    # The tool will return 5,000+ characters, but the AgentRunner will intercept it.
    fetch_tool = Tool(
        name="fetch_huge_logs",
        description="Fetch server logs for a given server name.",
        func=fetch_huge_logs,
        schema={
            "type": "function",
            "function": {
                "name": "fetch_huge_logs",
                "description": "Fetch server logs.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "server_name": {"type": "string"}
                    },
                    "required": ["server_name"]
                }
            }
        },
        max_result_length=200 
    )
    
    agent = Agent(
        name="DevOpsBot",
        description="A bot that analyzes logs.",
        system_prompt="You are a helpful DevOps assistant. If a tool output is truncated, YOU MUST explicitly use the `read_file_chunk` tool to read the rest of the artifact file from disk! Read it in chunks of 500 characters until you find the problem.",
        provider=provider,
        memory=InMemoryStore(),
        session_id="truncation_session_1",
        tools=[fetch_tool],
        compaction=KeepAllStrategy()
    )
    
    print("🤖 Agent Initialized with fetch_huge_logs (max_result_length=200)")
    print("-------------------------------------------------------------------")
    
    # We ask the agent to fetch the logs.
    await agent.aadd_message(Message(role="user", content="Can you fetch the logs for 'prod-server-1'? I need to know what the warnings are about."))
    
    # We let it run for 4 iterations so it can:
    # 1. Call fetch_huge_logs
    # 2. Get truncated!
    # 3. See the dynamic read_file_chunk tool get injected.
    # 4. Call read_file_chunk to get the rest of the data.
    agent.max_iterations = 15
    runner = AgentRunner(agent)
    await runner.arun()
    
    print("-------------------------------------------------------------------")
    print("Conversation Complete. Let's see the agent's final answer:")
    print(agent.messages[-1].content)
    
    # Cleanup the temp file for the demo
    import shutil
    try:
        shutil.rmtree("/tmp/orkestra_artifacts/truncation_session_1")
    except:
        pass

if __name__ == "__main__":
    asyncio.run(main())
