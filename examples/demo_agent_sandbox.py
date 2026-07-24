import asyncio
import os
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.core.messages import Message
from orkestra.core.tools import Tool
from orkestra.providers.gemini_provider import GeminiProvider

def execute_python_code(code: str):
    """Executes arbitrary python code."""
    # We use exec to run the code, and capture the output
    import sys
    from io import StringIO
    
    old_stdout = sys.stdout
    redirected_output = sys.stdout = StringIO()
    
    try:
        exec(code)
    except Exception as e:
        sys.stdout = old_stdout
        return f"Error executing code: {str(e)}"
        
    sys.stdout = old_stdout
    return redirected_output.getvalue()

async def run_demo():
    print("=== Orkestra Agent Sandbox Hardening Demo ===")
    
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # We provide the agent with a python REPL tool
    python_repl = Tool(
        name="python_repl",
        description="Execute arbitrary python code. Returns stdout.",
        func=execute_python_code,
        schema={
            "type": "function",
            "function": {
                "name": "python_repl",
                "description": "Execute arbitrary python code. Returns stdout.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "code": {"type": "string", "description": "The python code to execute"}
                    },
                    "required": ["code"]
                }
            }
        },
        timeout_seconds=5,
        network_access=False
    )
    
    agent = Agent(
        name="SandboxedBot",
        description="I am an agent running in a hardened sandbox.",
        system_prompt="You are a helpful assistant. Use the python_repl tool to execute code when requested by the user.",
        provider=provider,
        tools=[python_repl]
    )
    
    runner = AgentRunner(agent)
    
    print("\n🗣️ User: Please write a python script that connects to 'http://google.com' and fetches the HTML. Use your python_repl tool and the standard 'urllib' library.")
    await agent.aadd_message(Message(role="user", content="Please write a python script that connects to 'http://google.com' and fetches the HTML. Use your python_repl tool and the standard 'urllib' library."))
    
    print("🤖 Agent is thinking... (It will attempt to run the malicious code, the framework will block it, and the agent should gracefully tell us it failed)")
    
    response = await runner.arun()
    
    print("\n✅ Final Response:")
    print(response.message.content)

if __name__ == "__main__":
    asyncio.run(run_demo())
