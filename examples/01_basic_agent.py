import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message

async def main():
    print("=== Orkestra: 01 Basic Agent ===")
    
    # 1. Initialize the Provider
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 2. Define the Agent
    agent = Agent(
        name="Greeter",
        description="A friendly greeter agent",
        system_prompt="You are a friendly, enthusiastic AI. Keep your response to one short sentence.",
        provider=provider
    )
    
    # 3. Add a user message and step the agent
    print("\nUser: Say hi to the world!")
    await agent.aadd_message(Message(role="user", content="Say hi to the world!"))
    
    response = await agent.astep()
    
    # 4. Print the result and token usage
    print(f"Greeter: {response.message.content}")
    print(f"\n[Token Usage: {agent.usage['prompt_tokens']} prompt, {agent.usage['completion_tokens']} completion]")

if __name__ == "__main__":
    asyncio.run(main())
