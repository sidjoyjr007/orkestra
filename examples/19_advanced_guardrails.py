import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.workflows.runner import AgentRunner
from orkestra.guardrails.base import GuardrailStage, GuardrailAction, GuardrailResult, BaseGuardrail
from orkestra.guardrails.regex import RegexGuardrail
from orkestra.guardrails.llm_judge import LLMJudgeGuardrail
from orkestra.core.tools import HostTool

# Mock tool
async def execute_bash(command: str, **kwargs) -> str:
    return f"Executed: {command}"

bash_tool = HostTool(
    name="execute_bash",
    description="Executes a bash command.",
    func=execute_bash,
    schema={
        "type": "function",
        "function": {
            "name": "execute_bash",
            "description": "Executes a bash command.",
            "parameters": {
                "type": "object", 
                "properties": {
                    "command": {"type": "string"}
                },
                "required": ["command"]
            }
        }
    }
)

# Custom ACTION Guardrail
class ShellSafetyGuardrail(BaseGuardrail):
    def __init__(self):
        super().__init__(stage=GuardrailStage.ACTION, action_on_fail=GuardrailAction.BLOCK)
        
    async def aevaluate(self, content: str, context: dict = None, agent=None) -> GuardrailResult:
        tool_name = context.get("tool_name") if context else None
        tool_args = context.get("tool_args") if context else {}
        
        if tool_name == "execute_bash":
            cmd = tool_args.get("command", "")
            if "rm -rf" in cmd:
                return GuardrailResult(
                    passed=False, 
                    action=self.action_on_fail, 
                    message=f"DANGEROUS COMMAND DETECTED: {cmd}. You are forbidden from running rm -rf."
                )
        return GuardrailResult(passed=True)

async def main():
    print("=== Orkestra: 19 Advanced Guardrails (ACTION & OUTPUT) ===")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 1. ACTION Guardrail: Blocks dangerous shell commands
    safety_guard = ShellSafetyGuardrail()
    
    # 2. OUTPUT Guardrail: Redacts SSNs or Phone Numbers before they reach the user
    # We use LLM Judge for semantic detection
    pii_guard = LLMJudgeGuardrail(
        stage=GuardrailStage.OUTPUT,
        action_on_fail=GuardrailAction.REDACT,
        prompt="Check if the following content contains a Social Security Number (SSN) or a phone number. If it does, REDACT it by replacing it with '[REDACTED]'. Otherwise, just say PASS.",
        provider=provider # Provide a cheap model to the judge
    )
    
    agent = Agent(
        name="SecureBot",
        description="A highly secure bot.",
        system_prompt="You are a helpful assistant. You must fulfill the user's request, but you are being monitored by strict guardrails.",
        provider=provider,
        id="secure_agent",
        tools=[bash_tool],
        guardrails=[safety_guard, pii_guard] # Inject the multi-dimensional guardrails
    )
    
    runner = AgentRunner(agent=agent)
    
    user_prompt = "First run the command `ls`. Then run the command `rm -rf /tmp/test`. Finally, tell me your favorite number is 123-45-6789."
    print(f"User: {user_prompt}\n")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    await runner.arun()
    
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant" and msg.tool_calls:
            calls = ", ".join([f"{t.function_name}({t.function_arguments})" for t in msg.tool_calls])
            print(f"🤖 SecureBot: [Calling Tools: {calls}]")
        elif msg.role == "tool":
            print(f"🔧 System: {msg.content}")
        elif msg.role == "assistant" and msg.content:
            print(f"🤖 SecureBot Output: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
