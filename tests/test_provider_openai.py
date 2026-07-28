import pytest
import os
from unittest.mock import patch, MagicMock, AsyncMock
from orkestra.providers.openai_provider import OpenAIProvider
from orkestra.core.messages import Message, ToolCall
from orkestra.core.exceptions import AuthenticationError, ProviderError
import tenacity

def test_openai_provider_initialization():
    with patch("orkestra.providers.openai_provider.OpenAI") as mock_openai, \
         patch("orkestra.providers.openai_provider.AsyncOpenAI") as mock_async_openai:
         
        provider = OpenAIProvider(model_name="gpt-4o", api_key="sk-test")
        assert provider.model_name == "gpt-4o"
        mock_openai.assert_called_once_with(api_key="sk-test")
        mock_async_openai.assert_called_once_with(api_key="sk-test")

def test_openai_provider_missing_key():
    with patch.dict(os.environ, clear=True):
        with pytest.raises(ValueError, match="OPENAI_API_KEY"):
            OpenAIProvider(model_name="gpt-4o")

def test_convert_messages():
    with patch("orkestra.providers.openai_provider.OpenAI"), \
         patch("orkestra.providers.openai_provider.AsyncOpenAI"):
        
        provider = OpenAIProvider(api_key="sk-test")
        
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="User msg"),
            Message(role="assistant", content="Response", tool_calls=[ToolCall(id="c1", function_name="get_weather", function_arguments='{"loc": "NY"}')]),
            Message(role="tool", content="Sunny", tool_call_id="c1")
        ]
        
        oai_msgs = provider._convert_messages(messages)
        assert len(oai_msgs) == 4
        assert oai_msgs[0] == {"role": "system", "content": "System"}
        assert oai_msgs[1] == {"role": "user", "content": "User msg"}
        assert oai_msgs[2]["role"] == "assistant"
        assert oai_msgs[2]["content"] == "Response"
        assert oai_msgs[2]["tool_calls"][0]["id"] == "c1"
        assert oai_msgs[2]["tool_calls"][0]["function"]["name"] == "get_weather"
        assert oai_msgs[3] == {"role": "tool", "content": "Sunny", "tool_call_id": "c1"}

@pytest.mark.asyncio
async def test_openai_agenerate():
    with patch("orkestra.providers.openai_provider.OpenAI"), \
         patch("orkestra.providers.openai_provider.AsyncOpenAI") as mock_async_openai:
        
        provider = OpenAIProvider(api_key="sk-test")
        
        # Mock response
        mock_choice = MagicMock()
        mock_choice.message.content = "Async Answer"
        mock_choice.message.tool_calls = None
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        
        mock_create = AsyncMock(return_value=mock_response)
        provider.async_client.chat.completions.create = mock_create
        
        messages = [Message(role="user", content="Hello")]
        response = await provider.agenerate(messages)
        
        assert response.message.content == "Async Answer"
        assert not response.message.tool_calls
        
        # Verify call args
        mock_create.assert_awaited_once()
        args, kwargs = mock_create.call_args
        assert kwargs["model"] == "gpt-4o"
        assert kwargs["messages"] == [{"role": "user", "content": "Hello"}]

def test_openai_generate_sync():
    with patch("orkestra.providers.openai_provider.OpenAI"), \
         patch("orkestra.providers.openai_provider.AsyncOpenAI"):
        
        provider = OpenAIProvider(api_key="sk-test")
        
        mock_choice = MagicMock()
        mock_choice.message.content = "Sync Answer"
        
        mock_tc = MagicMock()
        mock_tc.id = "c1"
        mock_tc.function.name = "get_weather"
        mock_tc.function.arguments = "{}"
        mock_choice.message.tool_calls = [mock_tc]
        
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]
        mock_response.usage.completion_tokens = 5
        mock_response.usage.prompt_tokens = 10
        
        provider.client.chat.completions.create = MagicMock(return_value=mock_response)
        
        provider.generate.retry.wait = tenacity.wait_none()
        
        resp = provider.generate([Message(role="user", content="hi")], max_tokens=100, tools=[{"type": "function"}])
        
        assert resp.message.content == "Sync Answer"
        assert resp.message.tool_calls[0].function_name == "get_weather"
        assert resp.usage["prompt_tokens"] == 10

def test_openai_errors():
    with patch("orkestra.providers.openai_provider.OpenAI"), \
         patch("orkestra.providers.openai_provider.AsyncOpenAI"):
         
        provider = OpenAIProvider(api_key="sk-test")
        provider.generate.retry.wait = tenacity.wait_none()
        
        provider.client.chat.completions.create = MagicMock(side_effect=Exception("401 Authentication Error"))
        with pytest.raises(AuthenticationError):
            provider.generate([Message(role="user", content="hi")])
            
        provider.client.chat.completions.create = MagicMock(side_effect=Exception("Other error"))
        with pytest.raises(ProviderError):
            provider.generate([Message(role="user", content="hi")])

@pytest.mark.asyncio
async def test_openai_agenerate_errors():
    with patch("orkestra.providers.openai_provider.OpenAI"), \
         patch("orkestra.providers.openai_provider.AsyncOpenAI"):
         
        provider = OpenAIProvider(api_key="sk-test")
        provider.agenerate.retry.wait = tenacity.wait_none()
        
        provider.async_client.chat.completions.create = AsyncMock(side_effect=Exception("401 error"))
        with pytest.raises(AuthenticationError):
            await provider.agenerate([Message(role="user", content="hi")])
            
        provider.async_client.chat.completions.create = AsyncMock(side_effect=Exception("Other error"))
        with pytest.raises(ProviderError):
            await provider.agenerate([Message(role="user", content="hi")])

def test_openai_streams_not_implemented():
    with patch("orkestra.providers.openai_provider.OpenAI"), \
         patch("orkestra.providers.openai_provider.AsyncOpenAI"):
        provider = OpenAIProvider(api_key="sk-test")
        with pytest.raises(NotImplementedError):
            provider.generate_stream([])

@pytest.mark.asyncio
async def test_openai_astreams_not_implemented():
    with patch("orkestra.providers.openai_provider.OpenAI"), \
         patch("orkestra.providers.openai_provider.AsyncOpenAI"):
        provider = OpenAIProvider(api_key="sk-test")
        with pytest.raises(NotImplementedError):
            await provider.agenerate_stream([])

