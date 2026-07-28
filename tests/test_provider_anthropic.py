import pytest
import os
import json
from unittest.mock import patch, MagicMock, AsyncMock
from orkestra.providers.anthropic_provider import AnthropicProvider
from orkestra.core.messages import Message, ToolCall

def test_anthropic_provider_initialization():
    with patch("orkestra.providers.anthropic_provider.Anthropic") as mock_anthropic, \
         patch("orkestra.providers.anthropic_provider.AsyncAnthropic") as mock_async_anthropic:
         
        provider = AnthropicProvider(model_name="claude-3-5-sonnet-20240620", api_key="sk-test")
        assert provider.model_name == "claude-3-5-sonnet-20240620"
        mock_anthropic.assert_called_once_with(api_key="sk-test")
        mock_async_anthropic.assert_called_once_with(api_key="sk-test")

def test_anthropic_provider_missing_key():
    with patch.dict(os.environ, clear=True):
        with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
            AnthropicProvider(model_name="claude")

def test_anthropic_convert_messages():
    with patch("orkestra.providers.anthropic_provider.Anthropic"), \
         patch("orkestra.providers.anthropic_provider.AsyncAnthropic"):
        
        provider = AnthropicProvider(api_key="sk-test")
        
        messages = [
            Message(role="system", content="System"),
            Message(role="user", content="User msg"),
            Message(role="assistant", content="Response", tool_calls=[ToolCall(id="c1", function_name="get_weather", function_arguments='{"loc": "NY"}')]),
            Message(role="tool", content="Sunny", tool_call_id="c1")
        ]
        
        sys, ant_msgs = provider._convert_messages(messages)
        assert sys == "System"
        assert len(ant_msgs) == 3
        assert ant_msgs[0] == {"role": "user", "content": "User msg"}
        
        assert ant_msgs[1]["role"] == "assistant"
        assert len(ant_msgs[1]["content"]) == 2
        assert ant_msgs[1]["content"][0]["type"] == "text"
        assert ant_msgs[1]["content"][1]["type"] == "tool_use"
        assert ant_msgs[1]["content"][1]["name"] == "get_weather"
        
        assert ant_msgs[2]["role"] == "user"
        assert ant_msgs[2]["content"][0]["type"] == "tool_result"
        assert ant_msgs[2]["content"][0]["tool_use_id"] == "c1"

@pytest.mark.asyncio
async def test_anthropic_agenerate():
    with patch("orkestra.providers.anthropic_provider.Anthropic"), \
         patch("orkestra.providers.anthropic_provider.AsyncAnthropic") as mock_async_anthropic:
        
        provider = AnthropicProvider(api_key="sk-test")
        
        # Mock response
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Async Answer"
        
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "c1"
        mock_tool_block.name = "get_weather"
        mock_tool_block.input = {"loc": "NY"}
        
        mock_response = MagicMock()
        mock_response.content = [mock_text_block, mock_tool_block]
        
        mock_create = AsyncMock(return_value=mock_response)
        provider.async_client.messages.create = mock_create
        
        messages = [Message(role="user", content="Hello")]
        response = await provider.agenerate(messages)
        
        assert response.message.content == "Async Answer"
        assert len(response.message.tool_calls) == 1
        assert response.message.tool_calls[0].function_name == "get_weather"
        assert json.loads(response.message.tool_calls[0].function_arguments)["loc"] == "NY"
        
        # Verify call args
        mock_create.assert_awaited_once()

def test_anthropic_convert_tools():
    provider = AnthropicProvider(api_key="sk-test")
    tools = [
        {
            "type": "function",
            "function": {
                "name": "get_weather",
                "description": "desc",
                "parameters": {"type": "object", "properties": {}}
            }
        },
        {"type": "not_function"}
    ]
    ant_tools = provider._convert_tools(tools)
    assert len(ant_tools) == 1
    assert ant_tools[0]["name"] == "get_weather"
    assert ant_tools[0]["description"] == "desc"
    assert ant_tools[0]["input_schema"]["type"] == "object"

def test_anthropic_generate_sync():
    with patch("orkestra.providers.anthropic_provider.Anthropic"), \
         patch("orkestra.providers.anthropic_provider.AsyncAnthropic"):
        
        import tenacity
        provider = AnthropicProvider(api_key="sk-test")
        provider.generate.retry.wait = tenacity.wait_none()
        
        mock_text_block = MagicMock()
        mock_text_block.type = "text"
        mock_text_block.text = "Sync Answer"
        
        mock_tool_block = MagicMock()
        mock_tool_block.type = "tool_use"
        mock_tool_block.id = "c1"
        mock_tool_block.name = "get_weather"
        mock_tool_block.input = {"loc": "NY"}
        
        mock_response = MagicMock()
        mock_response.content = [mock_text_block, mock_tool_block]
        mock_response.usage.output_tokens = 5
        mock_response.usage.input_tokens = 10
        
        provider.client.messages.create = MagicMock(return_value=mock_response)
        
        resp = provider.generate([Message(role="user", content="hi")], tools=[{"type": "function", "function": {"name": "get_weather"}}])
        
        assert resp.message.content == "Sync Answer"
        assert resp.message.tool_calls[0].function_name == "get_weather"
        assert resp.usage["prompt_tokens"] == 10
        assert resp.usage["completion_tokens"] == 5

def test_anthropic_errors():
    with patch("orkestra.providers.anthropic_provider.Anthropic"), \
         patch("orkestra.providers.anthropic_provider.AsyncAnthropic"):
         
        import tenacity
        from orkestra.core.exceptions import AuthenticationError, ProviderError
        provider = AnthropicProvider(api_key="sk-test")
        provider.generate.retry.wait = tenacity.wait_none()
        
        provider.client.messages.create = MagicMock(side_effect=Exception("401 Authentication Error"))
        with pytest.raises(AuthenticationError):
            provider.generate([Message(role="user", content="hi")])
            
        provider.client.messages.create = MagicMock(side_effect=Exception("Other error"))
        with pytest.raises(ProviderError):
            provider.generate([Message(role="user", content="hi")])

@pytest.mark.asyncio
async def test_anthropic_agenerate_errors():
    with patch("orkestra.providers.anthropic_provider.Anthropic"), \
         patch("orkestra.providers.anthropic_provider.AsyncAnthropic"):
         
        import tenacity
        from orkestra.core.exceptions import AuthenticationError, ProviderError
        provider = AnthropicProvider(api_key="sk-test")
        provider.agenerate.retry.wait = tenacity.wait_none()
        
        provider.async_client.messages.create = AsyncMock(side_effect=Exception("401 error"))
        with pytest.raises(AuthenticationError):
            await provider.agenerate([Message(role="user", content="hi")])
            
        provider.async_client.messages.create = AsyncMock(side_effect=Exception("Other error"))
        with pytest.raises(ProviderError):
            await provider.agenerate([Message(role="user", content="hi")])

def test_anthropic_streams_not_implemented():
    with patch("orkestra.providers.anthropic_provider.Anthropic"), \
         patch("orkestra.providers.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(api_key="sk-test")
        with pytest.raises(NotImplementedError):
            provider.generate_stream([])

@pytest.mark.asyncio
async def test_anthropic_astreams_not_implemented():
    with patch("orkestra.providers.anthropic_provider.Anthropic"), \
         patch("orkestra.providers.anthropic_provider.AsyncAnthropic"):
        provider = AnthropicProvider(api_key="sk-test")
        with pytest.raises(NotImplementedError):
            await provider.agenerate_stream([])
