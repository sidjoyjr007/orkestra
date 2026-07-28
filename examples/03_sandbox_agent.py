import asyncio
import os
import json
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.tools import Tool
from orkestra.workflows.runner import AgentRunner

# 1. Define the Python function that will execute INSIDE the Docker Sandbox
# Orkestra will automatically package this function, spin up an ephemeral container,
# drop all privileges, and run this function inside it.
def run_sandbox(code: str, **kwargs) -> str:
    import subprocess
    
    # Write to /tmp because the sandbox runs as a restricted user (1000:1000)
    # and the default /app directory is owned by root!
    script_path = "/tmp/temp_script.py"
    with open(script_path, "w") as f:
        f.write(code)
        
    try:
        # Run the AI's code
        res = subprocess.run(["python", script_path], capture_output=True, text=True, timeout=5)
        if res.returncode != 0:
            return f"Error executing script:\n{res.stderr}"
        return f"Output:\n{res.stdout}"
    except Exception as e:
        return f"System Error:\n{str(e)}"

# 2. Wrap it in Orkestra's base `Tool` class (which natively wraps it in Docker)
python_sandbox_tool = Tool(
    name="python_eval",
    description="Write and execute Python 3 code in a secure sandboxed environment. Pass the raw python script as the 'code' parameter.",
    func=run_sandbox,
    schema={
        "type": "function",
        "function": {
            "name": "python_eval",
            "description": "Execute a python script.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"}
                },
                "required": ["code"]
            }
        }
    },
    network_access=False,  # Completely isolated from the internet
    timeout_seconds=10     # Kill the container if it hangs
)

async def main():
    print("=== Orkestra: 03 Sandbox Agent ===\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 3. Create the Agent
    agent = Agent(
        name="DataScientist",
        description="An AI capable of writing and executing complex python scripts.",
        system_prompt=(
            "You are a brilliant Data Scientist. You MUST use the `python_eval` tool to "
            "write and run a Python script to calculate the answers to complex math questions. "
            "Use print() in your script to output the result so you can read it."
        ),
        provider=provider,
        tools=[python_sandbox_tool]
    )
    
    runner = AgentRunner(agent=agent)
    
    user_prompt = "What is the 100th Fibonacci number? Write a script to calculate it."
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    print("Running Sandboxed Agent loop... (this will spin up a docker container!)\n")
    await runner.arun()
    
    # Print the final conversation history
    print("--- Execution History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            print(f"🤖 DataScientist: [Generated Python Script -> Sending to Docker Sandbox]")
            try:
                args = json.loads(msg.tool_calls[0].function_arguments)
                code = args.get("code", "")
                print(f"--- Script Preview ---\n{code}\n----------------------")
            except:
                pass
        elif msg.role == "tool":
            res = msg.content
            if len(res) > 300:
                res = res[:300] + "... [TRUNCATED]"
            print(f"🐳 Docker Sandbox Result: {res}")
        elif msg.role == "assistant":
            print(f"🤖 DataScientist: {msg.content}")
            
    print(f"\n[Token Usage: {agent.usage['prompt_tokens']} prompt, {agent.usage['completion_tokens']} completion]")

if __name__ == "__main__":
    asyncio.run(main())
