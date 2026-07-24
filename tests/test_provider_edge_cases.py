import pytest
from unittest.mock import patch, AsyncMock
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.exceptions import RateLimitError, ProviderError
from orkestra.events.base import ProviderRetrying

@pytest.mark.asyncio
async def test_exponential_backoff_and_retry(event_bus):
    provider = GeminiProvider(model_name="test", api_key="test", event_bus=event_bus)
    
    events_caught = []
    def on_retry(event: ProviderRetrying):
        events_caught.append(event)
        
    event_bus.subscribe(ProviderRetrying, on_retry)
    
    # We will mock the Google GenAI client to throw a RateLimitError
    with patch("orkestra.providers.gemini_provider.genai.Client") as mock_client_cls:
        mock_client = mock_client_cls.return_value
        
        # AsyncMock for the aio.models.generate_content method
        mock_generate = AsyncMock()
        # Mock it to raise an Exception that will be caught and turned into ProviderError by the wrapper
        mock_generate.side_effect = Exception("Simulated API failure")
        
        mock_client.aio.models.generate_content = mock_generate
        
        # This should fail after 3 retries (total 3 attempts)
        with pytest.raises(ProviderError):
            # We override wait so tests run fast instead of actually waiting for exponential backoff
            with patch("orkestra.providers.gemini_provider.wait_exponential", return_value=0):
                await provider.agenerate([Message(role="user", content="hello")])
                
        # Tenacity stop_after_attempt(3) means it will try 3 times, fail on the 3rd.
        # It will emit a ProviderRetrying event on failures before sleep.
        # So it should emit 2 retry events.
        assert len(events_caught) >= 1
        assert events_caught[0].provider_name == "GeminiProvider"
