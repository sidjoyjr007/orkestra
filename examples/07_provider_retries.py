import asyncio
import os
from orkestra.providers import GeminiProvider
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.exceptions import ProviderError

# -------------------------------------------------------------------
# 1. Setup a Mock Network Flakiness
# -------------------------------------------------------------------
def inject_network_failures(provider: GeminiProvider):
    """
    Monkeypatch the provider to simulate a flaky network!
    We will force it to fail the first 2 times with a ProviderError (like a 503 or Rate Limit),
    and succeed on the 3rd attempt.
    """
    original_generate_content = provider.client.aio.models.generate_content
    provider.attempt_count = 0

    async def flaky_generate_content(*args, **kwargs):
        provider.attempt_count += 1
        if provider.attempt_count <= 2:
            print(f"\n[NETWORK MOCK] Simulating a 503 Service Unavailable (Attempt {provider.attempt_count})...")
            # Orkestra's @_handle_gemini_errors decorator catches generic exceptions and maps them to ProviderError
            # But the @with_retry decorator also catches standard ProviderErrors directly!
            raise ProviderError("503 Service Unavailable: The model is overloaded.")
        
        print(f"\n[NETWORK MOCK] Simulating a successful connection (Attempt {provider.attempt_count})...")
        return await original_generate_content(*args, **kwargs)

    # Apply the patch to the UNDERLYING Google client so the @with_retry decorator on agenerate still works!
    provider.client.aio.models.generate_content = flaky_generate_content

async def main():
    print("=== Orkestra: 07 Provider Retries & Backoff ===\n")
    print("In production, API rate limits (429) or timeouts (503) happen frequently.")
    print("Orkestra Providers use `tenacity` under the hood to automatically apply exponential backoff!\n")
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Please set GEMINI_API_KEY environment variable.")
        return
        
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    inject_network_failures(provider)
    
    agent = Agent(
        name="ResilientBot",
        description="A bot that survives network outages.",
        system_prompt="You are a helpful assistant.",
        provider=provider
    )
    
    user_prompt = "Say 'Hello World'!"
    print(f"User: {user_prompt}")
    await agent.aadd_message(Message(role="user", content=user_prompt))
    
    # Watch how the agent runner handles the failures natively!
    await agent.astep()
    
    print("\n--- Final Chat History ---")
    for msg in agent.messages:
        if msg.role == "assistant":
            print(f"🤖 ResilientBot: {msg.content}")

if __name__ == "__main__":
    asyncio.run(main())
