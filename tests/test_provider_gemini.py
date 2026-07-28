import pytest
import os
import json
from typing import AsyncIterator
from unittest.mock import patch, MagicMock, AsyncMock
from google.genai import types, errors

from orkestra.providers.gemini_provider import GeminiProvider, _publish_retry_event
from orkestra.core.messages import Message, ToolCall
from orkestra.core.exceptions import AuthenticationError, RateLimitError, ProviderError
from orkestra.events.base import ProviderRetrying

def test_gemini_provider_initialization():
    with patch("orkestra.providers.gemini_provider.genai.Client") as mock_client:
        provider = GeminiProvider(model_name="gemini-2.5-pro", api_key="sk-test")
        assert provider.model_name == "gemini-2.5-pro"
        mock_client.assert_called_once_with(api_key="sk-test")

@patch("orkestra.providers.gemini_provider.types")
def test_gemini_format_messages(mock_types):
    provider = GeminiProvider(api_key="sk-test")
    messages = [
        Message(role="system", content="System"),
        Message(role="user", content="User msg"),
        Message(role="assistant", content="Response", tool_calls=[ToolCall(id="c1", function_name="get_weather", function_arguments='{"loc": "NY"}')]),
        Message(role="tool", content="Sunny", tool_call_id="c1", name="get_weather")
    ]
    
    formatted = provider._format_messages(messages)
    assert len(formatted) == 3 # system skipped

def test_gemini_convert_tools():
    provider = GeminiProvider(api_key="sk-test")
    tools_json = [
        {
            "type": "function",
            "function": {
                "name": "get_data",
                "description": "desc",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "p1": {"type": "string"},
                        "p2": {"type": "integer"},
                        "p3": {"type": "number"},
                        "p4": {"type": "boolean"},
                        "p5": {"type": "array", "items": {"type": "string"}},
                        "p6": {"type": "array", "items": {"type": "integer"}},
                        "p7": {"type": "object"},
                        "p8": {"type": "unknown"}
                    },
                    "required": ["p1"]
                }
            }
        }
    ]
    
    gemini_tools = provider._convert_tools_to_gemini(tools_json)
    assert gemini_tools is not None
    assert len(gemini_tools) == 1

def test_gemini_convert_tools_empty():
    provider = GeminiProvider(api_key="sk-test")
    assert provider._convert_tools_to_gemini([]) is None

def test_gemini_extract_system_instruction():
    provider = GeminiProvider(api_key="sk-test")
    msgs = [Message(role="system", content="Be nice"), Message(role="system", content="Be smart")]
    assert provider._extract_system_instruction(msgs) == "Be nice\nBe smart"

def test_publish_retry_event():
    # Test retry event publisher
    mock_retry_state = MagicMock()
    mock_retry_state.outcome.exception.return_value = Exception("fail")
    mock_retry_state.attempt_number = 2
    mock_retry_state.idle_for = 1.5
    
    mock_provider = MagicMock()
    mock_provider.__class__.__name__ = "GeminiProvider"
    mock_provider.event_bus = MagicMock()
    
    mock_retry_state.args = [mock_provider]
    
    _publish_retry_event(mock_retry_state)
    mock_provider.event_bus.publish.assert_called_once()
    assert isinstance(mock_provider.event_bus.publish.call_args[0][0], ProviderRetrying)

def test_gemini_errors():
    import tenacity
    provider = GeminiProvider(api_key="sk-test")
    provider.generate.retry.wait = tenacity.wait_none()
    
    # Force client to throw errors
    def mock_fail(*args, **kwargs):
        raise errors.APIError(401, "401 unauthenticated")
    provider.client.models.generate_content = mock_fail
    
    with pytest.raises(AuthenticationError):
        provider.generate([Message(role="user", content="hi")])

    def mock_fail_429(*args, **kwargs):
        raise errors.APIError(429, "429 quota exceeded")
    provider.client.models.generate_content = mock_fail_429
    
    with pytest.raises(RateLimitError):
        provider.generate([Message(role="user", content="hi")])

    def mock_fail_400(*args, **kwargs):
        raise errors.APIError(400, "invalid argument")
    provider.client.models.generate_content = mock_fail_400
    
    with pytest.raises(ProviderError):
        provider.generate([Message(role="user", content="hi")])

    def mock_fail_gen(*args, **kwargs):
        raise Exception("Random error")
    provider.client.models.generate_content = mock_fail_gen
    
    with pytest.raises(ProviderError):
        provider.generate([Message(role="user", content="hi")])

def test_gemini_generate_sync():
    provider = GeminiProvider(api_key="sk-test")
    
    mock_response = MagicMock()
    mock_candidate = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "Sync Answer"
    mock_candidate.content.parts = [mock_part]
    mock_candidate.finish_reason.name = "STOP"
    mock_response.candidates = [mock_candidate]
    mock_response.function_calls = []
    
    mock_usage = MagicMock()
    mock_usage.prompt_token_count = 10
    mock_usage.candidates_token_count = 5
    mock_usage.total_token_count = 15
    mock_response.usage_metadata = mock_usage
    
    provider.client.models.generate_content = MagicMock(return_value=mock_response)
    
    resp = provider.generate([Message(role="user", content="hi")], tools=[{"type": "function", "function": {"name": "f", "parameters": {}}}])
    
    assert resp.message.content == "Sync Answer"
    assert resp.usage["prompt_tokens"] == 10
    assert resp.usage["total_tokens"] == 15

def test_gemini_generate_stream():
    provider = GeminiProvider(api_key="sk-test")
    
    mock_chunk = MagicMock()
    mock_chunk.text = "chunk1"
    mock_chunk.function_calls = []
    mock_chunk.candidates[0].finish_reason.name = "STOP"
    
    provider.client.models.generate_content_stream = MagicMock(return_value=[mock_chunk])
    
    chunks = list(provider.generate_stream([Message(role="user", content="hi")], tools=[{"type": "function", "function": {"name": "f", "parameters": {}}}]))
    
    assert len(chunks) == 1
    assert chunks[0].content == "chunk1"

@pytest.mark.asyncio
async def test_gemini_agenerate():
    provider = GeminiProvider(api_key="sk-test")
    
    mock_response = MagicMock()
    mock_part = MagicMock()
    mock_part.text = "Async Answer"
    mock_part.function_call.name = "get_weather"
    mock_part.function_call.args = {"loc": "NY"}
    
    mock_candidate = MagicMock()
    mock_candidate.content.parts = [mock_part]
    mock_candidate.finish_reason.name = "STOP"
    mock_response.candidates = [mock_candidate]
    mock_response.function_calls = [mock_part.function_call]
    mock_response.usage_metadata = None
    
    provider.client.aio.models.generate_content = AsyncMock(return_value=mock_response)
    
    response = await provider.agenerate([Message(role="user", content="Hello")])
    
    assert response.message.content == "Async Answer"
    assert len(response.message.tool_calls) == 1
    assert response.message.tool_calls[0].function_name == "get_weather"

@pytest.mark.asyncio
async def test_gemini_agenerate_stream():
    provider = GeminiProvider(api_key="sk-test")
    
    mock_chunk = MagicMock()
    mock_chunk.text = "async_chunk"
    
    mock_fc = MagicMock()
    mock_fc.name = "func_1"
    mock_fc.args = {"a": 1}
    mock_chunk.function_calls = [mock_fc]
    mock_chunk.candidates[0].finish_reason.name = "STOP"
    
    async def mock_stream():
        yield mock_chunk
        
    provider.client.aio.models.generate_content_stream = AsyncMock(return_value=mock_stream())
    
    chunks = []
    async for c in provider.agenerate_stream([Message(role="user", content="hi")]):
        chunks.append(c)
        
    assert len(chunks) == 1
    assert chunks[0].content == "async_chunk"
    assert chunks[0].tool_calls[0].function_name == "func_1"
