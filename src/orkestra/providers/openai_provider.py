import os
import json
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
from openai import OpenAI, AsyncOpenAI
from orkestra.providers.base import BaseProvider
from orkestra.core.messages import Message, Response, ResponseChunk, ToolCall
from orkestra.core.exceptions import ProviderError, AuthenticationError
import tenacity

class OpenAIProvider(BaseProvider):
    """OpenAI API provider for Orkestra."""

    def __init__(self, model_name: str = "gpt-4o", api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, **kwargs)
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY must be provided or set in environment.")
        self.client = OpenAI(api_key=self.api_key)
        self.async_client = AsyncOpenAI(api_key=self.api_key)

    def _convert_messages(self, messages: List[Message]) -> List[Dict[str, Any]]:
        oai_messages = []
        for msg in messages:
            if msg.role == "user":
                oai_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                oai_msg = {"role": "assistant", "content": msg.content or ""}
                if msg.tool_calls:
                    oai_msg["tool_calls"] = [
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
                oai_messages.append(oai_msg)
            elif msg.role == "tool":
                oai_messages.append({
                    "role": "tool",
                    "content": msg.content,
                    "tool_call_id": msg.tool_call_id,
                })
            elif msg.role == "system":
                oai_messages.append({"role": "system", "content": msg.content})
        return oai_messages

    @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def generate(self, messages: List[Message], temperature: float = 0.7, max_tokens: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Response:
        try:
            oai_messages = self._convert_messages(messages)
            request_kwargs = {
                "model": self.model_name,
                "messages": oai_messages,
                "temperature": temperature,
            }
            if max_tokens:
                request_kwargs["max_tokens"] = max_tokens
            if tools:
                request_kwargs["tools"] = tools

            response = self.client.chat.completions.create(**request_kwargs)
            choice = response.choices[0]
            
            tool_calls = []
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        function_name=tc.function.name,
                        function_arguments=tc.function.arguments
                    ))
                    
            content = choice.message.content or ""
            return Response(
                message=Message(role="assistant", content=content, tool_calls=tool_calls),
                usage={"completion_tokens": response.usage.completion_tokens, "prompt_tokens": response.usage.prompt_tokens} if response.usage else {}
            )
        except Exception as e:
            if "Authentication" in str(e):
                raise AuthenticationError(str(e)) from e
            raise ProviderError(str(e)) from e

    @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def agenerate(self, messages: List[Message], temperature: float = 0.7, max_tokens: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Response:
        try:
            oai_messages = self._convert_messages(messages)
            request_kwargs = {
                "model": self.model_name,
                "messages": oai_messages,
                "temperature": temperature,
            }
            if max_tokens:
                request_kwargs["max_tokens"] = max_tokens
            if tools:
                request_kwargs["tools"] = tools

            response = await self.async_client.chat.completions.create(**request_kwargs)
            choice = response.choices[0]
            
            tool_calls = []
            if choice.message.tool_calls:
                for tc in choice.message.tool_calls:
                    tool_calls.append(ToolCall(
                        id=tc.id,
                        function_name=tc.function.name,
                        function_arguments=tc.function.arguments
                    ))
                    
            content = choice.message.content or ""
            return Response(
                message=Message(role="assistant", content=content, tool_calls=tool_calls),
                usage={"completion_tokens": response.usage.completion_tokens, "prompt_tokens": response.usage.prompt_tokens} if response.usage else {}
            )
        except Exception as e:
            if "Authentication" in str(e) or "401" in str(e):
                raise AuthenticationError(str(e)) from e
            raise ProviderError(str(e)) from e

    def generate_stream(self, messages: List[Message], temperature: float = 0.7, max_tokens: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Iterator[ResponseChunk]:
        raise NotImplementedError("Streaming not yet implemented for OpenAIProvider")

    async def agenerate_stream(self, messages: List[Message], temperature: float = 0.7, max_tokens: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncIterator[ResponseChunk]:
        raise NotImplementedError("Streaming not yet implemented for OpenAIProvider")
