import os
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
import anthropic
from orkestra.core.messages import Message, Response, ResponseChunk, ToolCall
from orkestra.providers.base import BaseProvider
from orkestra.core.exceptions import (
    AuthenticationError, RateLimitError, ProviderError, ContextWindowExceededError
)
import functools
import asyncio

def _handle_anthropic_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(str(e)) from e
        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e)) from e
        except anthropic.BadRequestError as e:
            raise ProviderError(str(e)) from e
        except anthropic.APIError as e:
            raise ProviderError(str(e)) from e
        except Exception as e:
            raise ProviderError(str(e)) from e
    
    @functools.wraps(func)
    async def awrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except anthropic.AuthenticationError as e:
            raise AuthenticationError(str(e)) from e
        except anthropic.RateLimitError as e:
            raise RateLimitError(str(e)) from e
        except anthropic.BadRequestError as e:
            raise ProviderError(str(e)) from e
        except anthropic.APIError as e:
            raise ProviderError(str(e)) from e
        except Exception as e:
            raise ProviderError(str(e)) from e
            
    if asyncio.iscoroutinefunction(func):
        return awrapper
    return wrapper

class AnthropicProvider(BaseProvider):
    """Anthropic API provider implementation."""

    def __init__(self, model_name: str = "claude-3-5-sonnet-20240620", api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, **kwargs)
        self.client = anthropic.Anthropic(api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY"))
        self.aclient = anthropic.AsyncAnthropic(api_key=self.api_key or os.environ.get("ANTHROPIC_API_KEY"))

    def _format_messages(self, messages: List[Message]) -> tuple[str, List[Dict[str, Any]]]:
        """Returns (system_prompt, formatted_messages)."""
        system_prompt = ""
        formatted = []
        
        for msg in messages:
            if msg.role == "system":
                system_prompt += (msg.content or "") + "\n"
                continue
                
            msg_dict = {"role": msg.role, "content": msg.content or ""}
            
            if msg.tool_calls:
                content = []
                if msg.content:
                    content.append({"type": "text", "text": msg.content})
                for tc in msg.tool_calls:
                    import json
                    content.append({
                        "type": "tool_use",
                        "id": tc.id,
                        "name": tc.function_name,
                        "input": json.loads(tc.function_arguments) if tc.function_arguments else {}
                    })
                msg_dict["content"] = content
                
            if msg.role == "tool":
                msg_dict["role"] = "user"
                msg_dict["content"] = [{
                    "type": "tool_result",
                    "tool_use_id": msg.tool_call_id,
                    "content": msg.content
                }]

            formatted.append(msg_dict)
            
        return system_prompt.strip(), formatted

    @_handle_anthropic_errors
    def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Response:
        system, formatted_messages = self._format_messages(messages)
        
        request_kwargs = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            **kwargs
        }
        if system:
            request_kwargs["system"] = system
        if tools:
            request_kwargs["tools"] = tools

        response = self.client.messages.create(**request_kwargs)
        
        content = ""
        tool_calls = None
        
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                import json
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(ToolCall(
                    id=block.id,
                    function_name=block.name,
                    function_arguments=json.dumps(block.input)
                ))
                
        message = Message(
            role="assistant",
            content=content if content else None,
            tool_calls=tool_calls
        )
        
        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens
        }

        return Response(
            message=message,
            finish_reason=response.stop_reason,
            usage=usage
        )

    @_handle_anthropic_errors
    def generate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Iterator[ResponseChunk]:
        system, formatted_messages = self._format_messages(messages)
        
        request_kwargs = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            **kwargs
        }
        if system:
            request_kwargs["system"] = system
        if tools:
            request_kwargs["tools"] = tools

        with self.client.messages.stream(**request_kwargs) as stream:
            for event in stream:
                if event.type == "text_delta":
                    yield ResponseChunk(content=event.text_delta.text)
                elif event.type == "tool_use":
                    pass
                elif event.type == "message_stop":
                    yield ResponseChunk(finish_reason="stop")

    @_handle_anthropic_errors
    async def agenerate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Response:
        system, formatted_messages = self._format_messages(messages)
        
        request_kwargs = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            **kwargs
        }
        if system:
            request_kwargs["system"] = system
        if tools:
            request_kwargs["tools"] = tools

        response = await self.aclient.messages.create(**request_kwargs)
        
        content = ""
        tool_calls = None
        
        for block in response.content:
            if block.type == "text":
                content += block.text
            elif block.type == "tool_use":
                import json
                if tool_calls is None:
                    tool_calls = []
                tool_calls.append(ToolCall(
                    id=block.id,
                    function_name=block.name,
                    function_arguments=json.dumps(block.input)
                ))
                
        message = Message(
            role="assistant",
            content=content if content else None,
            tool_calls=tool_calls
        )
        
        usage = {
            "prompt_tokens": response.usage.input_tokens,
            "completion_tokens": response.usage.output_tokens,
            "total_tokens": response.usage.input_tokens + response.usage.output_tokens
        }

        return Response(
            message=message,
            finish_reason=response.stop_reason,
            usage=usage
        )

    @_handle_anthropic_errors
    async def agenerate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = 4096,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[ResponseChunk]:
        system, formatted_messages = self._format_messages(messages)
        
        request_kwargs = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "max_tokens": max_tokens or 4096,
            **kwargs
        }
        if system:
            request_kwargs["system"] = system
        if tools:
            request_kwargs["tools"] = tools

        async with self.aclient.messages.stream(**request_kwargs) as stream:
            async for event in stream:
                if event.type == "text_delta":
                    yield ResponseChunk(content=event.text_delta.text)
                elif event.type == "tool_use":
                    pass
                elif event.type == "message_stop":
                    yield ResponseChunk(finish_reason="stop")
