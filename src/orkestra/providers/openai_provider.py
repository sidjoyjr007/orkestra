import os
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
import openai
from orkestra.core.messages import Message, Response, ResponseChunk, ToolCall
from orkestra.providers.base import BaseProvider
from orkestra.core.exceptions import (
    AuthenticationError, RateLimitError, ProviderError, ContextWindowExceededError
)
import functools

def _handle_openai_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except openai.AuthenticationError as e:
            raise AuthenticationError(str(e)) from e
        except openai.RateLimitError as e:
            raise RateLimitError(str(e)) from e
        except openai.BadRequestError as e:
            # Often related to context window or invalid params
            if "context_length_exceeded" in str(e):
                raise ContextWindowExceededError(str(e)) from e
            raise ProviderError(str(e)) from e
        except openai.APIError as e:
            raise ProviderError(str(e)) from e
        except Exception as e:
            raise ProviderError(str(e)) from e
    
    @functools.wraps(func)
    async def awrapper(*args, **kwargs):
        try:
            if hasattr(func, '__aiter__') or str(type(func)) == "<class 'async_generator'>":
                # We handle streaming iterators differently below, but for simple async defs:
                pass
            return await func(*args, **kwargs)
        except openai.AuthenticationError as e:
            raise AuthenticationError(str(e)) from e
        except openai.RateLimitError as e:
            raise RateLimitError(str(e)) from e
        except openai.BadRequestError as e:
            if "context_length_exceeded" in str(e):
                raise ContextWindowExceededError(str(e)) from e
            raise ProviderError(str(e)) from e
        except openai.APIError as e:
            raise ProviderError(str(e)) from e
        except Exception as e:
            raise ProviderError(str(e)) from e
            
    if asyncio.iscoroutinefunction(func):
        return awrapper
    return wrapper

class OpenAIProvider(BaseProvider):
    """OpenAI API provider implementation."""

    def __init__(self, model_name: str = "gpt-4-turbo", api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, **kwargs)
        self.client = openai.OpenAI(api_key=self.api_key or os.environ.get("OPENAI_API_KEY"), **kwargs.get("client_kwargs", {}))
        self.aclient = openai.AsyncOpenAI(api_key=self.api_key or os.environ.get("OPENAI_API_KEY"), **kwargs.get("client_kwargs", {}))

    def _format_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        formatted = []
        for msg in messages:
            msg_dict = {"role": msg.role, "content": msg.content or ""}
            if msg.name:
                msg_dict["name"] = msg.name
            if msg.tool_calls:
                msg_dict["tool_calls"] = [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function_name,
                            "arguments": tc.function_arguments,
                        }
                    }
                    for tc in msg.tool_calls
                ]
            if msg.tool_call_id:
                msg_dict["tool_call_id"] = msg.tool_call_id
            formatted.append(msg_dict)
        return formatted

    @_handle_openai_errors
    def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Response:
        formatted_messages = self._format_messages(messages)
        
        request_kwargs = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            **kwargs
        }
        if max_tokens:
            request_kwargs["max_tokens"] = max_tokens
        if tools:
            request_kwargs["tools"] = tools

        completion = self.client.chat.completions.create(**request_kwargs)
        choice = completion.choices[0]
        
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    function_name=tc.function.name,
                    function_arguments=tc.function.arguments
                )
                for tc in choice.message.tool_calls
            ]
            
        message = Message(
            role="assistant",
            content=choice.message.content,
            tool_calls=tool_calls
        )
        
        usage = {}
        if completion.usage:
            usage = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens
            }

        return Response(
            message=message,
            finish_reason=choice.finish_reason,
            usage=usage
        )

    @_handle_openai_errors
    def generate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Iterator[ResponseChunk]:
        formatted_messages = self._format_messages(messages)
        
        request_kwargs = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        if max_tokens:
            request_kwargs["max_tokens"] = max_tokens
        if tools:
            request_kwargs["tools"] = tools

        stream = self.client.chat.completions.create(**request_kwargs)
        
        for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            
            tool_calls = None
            if choice.delta.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id or "",
                        function_name=tc.function.name or "",
                        function_arguments=tc.function.arguments or ""
                    )
                    for tc in choice.delta.tool_calls
                ]

            yield ResponseChunk(
                content=choice.delta.content,
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason
            )

    @_handle_openai_errors
    async def agenerate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Response:
        formatted_messages = self._format_messages(messages)
        
        request_kwargs = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            **kwargs
        }
        if max_tokens:
            request_kwargs["max_tokens"] = max_tokens
        if tools:
            request_kwargs["tools"] = tools

        completion = await self.aclient.chat.completions.create(**request_kwargs)
        choice = completion.choices[0]
        
        tool_calls = None
        if choice.message.tool_calls:
            tool_calls = [
                ToolCall(
                    id=tc.id,
                    function_name=tc.function.name,
                    function_arguments=tc.function.arguments
                )
                for tc in choice.message.tool_calls
            ]
            
        message = Message(
            role="assistant",
            content=choice.message.content,
            tool_calls=tool_calls
        )
        
        usage = {}
        if completion.usage:
            usage = {
                "prompt_tokens": completion.usage.prompt_tokens,
                "completion_tokens": completion.usage.completion_tokens,
                "total_tokens": completion.usage.total_tokens
            }

        return Response(
            message=message,
            finish_reason=choice.finish_reason,
            usage=usage
        )

    @_handle_openai_errors
    async def agenerate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[ResponseChunk]:
        formatted_messages = self._format_messages(messages)
        
        request_kwargs = {
            "model": self.model_name,
            "messages": formatted_messages,
            "temperature": temperature,
            "stream": True,
            **kwargs
        }
        if max_tokens:
            request_kwargs["max_tokens"] = max_tokens
        if tools:
            request_kwargs["tools"] = tools

        stream = await self.aclient.chat.completions.create(**request_kwargs)
        
        async for chunk in stream:
            if not chunk.choices:
                continue
            choice = chunk.choices[0]
            
            tool_calls = None
            if choice.delta.tool_calls:
                tool_calls = [
                    ToolCall(
                        id=tc.id or "",
                        function_name=tc.function.name or "",
                        function_arguments=tc.function.arguments or ""
                    )
                    for tc in choice.delta.tool_calls
                ]

            yield ResponseChunk(
                content=choice.delta.content,
                tool_calls=tool_calls,
                finish_reason=choice.finish_reason
            )
