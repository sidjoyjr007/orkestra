import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.workflows.runner import AgentRunner

async def main():
    print("=== Orkestra: 20 Agent-to-Agent (A2A) Protocol ===")
    print("Demonstrating raw A2A communication where two agents talk to each other.\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    # 1. Create two agents with opposing system prompts
    comedian = Agent(
        name="Comedian",
        description="Tells a setup to a joke.",
        system_prompt="You are a comedian. Tell the setup to a joke, but do NOT give the punchline. Just the setup. Keep it very short.",
        provider=provider,
        id="comedian_agent"
    )
    
    heckler = Agent(
        name="Heckler",
        description="Guesses the punchline to jokes.",
        system_prompt="You are an annoying audience member. A comedian will give you a joke setup. Try to guess the punchline. Keep it very short.",
        provider=provider,
        id="heckler_agent"
    )
    
    # We don't need the Orchestrator for simple A2A loops, just the runners!
    comedian_runner = AgentRunner(agent=comedian)
    heckler_runner = AgentRunner(agent=heckler)
    
    # 2. Kick off the conversation
    initial_prompt = "Tell your best joke setup."
    print(f"User: {initial_prompt}\n")
    await comedian.aadd_message(Message(role="user", content=initial_prompt))
    
    # Run the comedian to get the setup
    response = await comedian_runner.arun()
    joke_setup = response.message.content
    print(f"🤖 Comedian: {joke_setup}\n")
    
    # 3. A2A Communication: Pass the Comedian's output to the Heckler's memory!
    # We inject it as a "user" message so the Heckler responds to it.
    await heckler.aadd_message(Message(role="user", content=joke_setup))
    
    # Run the heckler to get the punchline guess
    response = await heckler_runner.arun()
    heckler_guess = response.message.content
    print(f"👿 Heckler: {heckler_guess}\n")
    
    # 4. A2A Communication: Pass the Heckler's guess back to the Comedian!
    await comedian.aadd_message(Message(role="user", content=f"The heckler guessed: '{heckler_guess}'. What is the actual punchline?"))
    
    response = await comedian_runner.arun()
    punchline = response.message.content
    print(f"🤖 Comedian: {punchline}\n")

if __name__ == "__main__":
    asyncio.run(main())
