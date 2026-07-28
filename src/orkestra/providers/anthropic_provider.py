import os
import json
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
from anthropic import Anthropic, AsyncAnthropic
from orkestra.providers.base import BaseProvider
from orkestra.core.messages import Message, Response, ResponseChunk, ToolCall
from orkestra.core.exceptions import ProviderError, AuthenticationError
import tenacity

class AnthropicProvider(BaseProvider):
    """Anthropic API provider for Orkestra."""

    def __init__(self, model_name: str = "claude-3-5-sonnet-20240620", api_key: Optional[str] = None, **kwargs):
        super().__init__(model_name, api_key, **kwargs)
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY must be provided or set in environment.")
        self.client = Anthropic(api_key=self.api_key)
        self.async_client = AsyncAnthropic(api_key=self.api_key)

    def _convert_messages(self, messages: List[Message]) -> tuple[str, List[Dict[str, Any]]]:
        system_prompt = ""
        anthropic_messages = []
        for msg in messages:
            if msg.role == "system":
                system_prompt += msg.content + "\n"
            elif msg.role == "user":
                anthropic_messages.append({"role": "user", "content": msg.content})
            elif msg.role == "assistant":
                content_blocks = []
                if msg.content:
                    content_blocks.append({"type": "text", "text": msg.content})
                if msg.tool_calls:
                    for tc in msg.tool_calls:
                        content_blocks.append({
                            "type": "tool_use",
                            "id": tc.id,
                            "name": tc.function_name,
                            "input": json.loads(tc.function_arguments) if tc.function_arguments else {}
                        })
                if content_blocks:
                    anthropic_messages.append({"role": "assistant", "content": content_blocks})
            elif msg.role == "tool":
                anthropic_messages.append({
                    "role": "user",
                    "content": [
                        {
                            "type": "tool_result",
                            "tool_use_id": msg.tool_call_id,
                            "content": msg.content
                        }
                    ]
                })
        return system_prompt.strip(), anthropic_messages

    def _convert_tools(self, tools: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        anthropic_tools = []
        for t in tools:
            # Orkestra tools are in OpenAI format: {"type": "function", "function": {"name": ..., "description": ..., "parameters": ...}}
            if "function" in t:
                func = t["function"]
                anthropic_tools.append({
                    "name": func["name"],
                    "description": func.get("description", ""),
                    "input_schema": func.get("parameters", {"type": "object", "properties": {}})
                })
        return anthropic_tools

    @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    def generate(self, messages: List[Message], temperature: float = 0.7, max_tokens: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Response:
        try:
            system_prompt, anthropic_messages = self._convert_messages(messages)
            request_kwargs = {
                "model": self.model_name,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }
            if system_prompt:
                request_kwargs["system"] = system_prompt
            if tools:
                request_kwargs["tools"] = self._convert_tools(tools)

            response = self.client.messages.create(**request_kwargs)
            
            tool_calls = []
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        function_name=block.name,
                        function_arguments=json.dumps(block.input)
                    ))
                    
            return Response(
                message=Message(role="assistant", content=content, tool_calls=tool_calls),
                usage={"completion_tokens": response.usage.output_tokens, "prompt_tokens": response.usage.input_tokens} if hasattr(response, "usage") else {}
            )
        except Exception as e:
            if "Authentication" in str(e) or "401" in str(e):
                raise AuthenticationError(str(e)) from e
            raise ProviderError(str(e)) from e

    @tenacity.retry(stop=tenacity.stop_after_attempt(3), wait=tenacity.wait_exponential(multiplier=1, min=2, max=10), reraise=True)
    async def agenerate(self, messages: List[Message], temperature: float = 0.7, max_tokens: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Response:
        try:
            system_prompt, anthropic_messages = self._convert_messages(messages)
            request_kwargs = {
                "model": self.model_name,
                "messages": anthropic_messages,
                "temperature": temperature,
                "max_tokens": max_tokens or 4096,
            }
            if system_prompt:
                request_kwargs["system"] = system_prompt
            if tools:
                request_kwargs["tools"] = self._convert_tools(tools)

            response = await self.async_client.messages.create(**request_kwargs)
            
            tool_calls = []
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text
                elif block.type == "tool_use":
                    tool_calls.append(ToolCall(
                        id=block.id,
                        function_name=block.name,
                        function_arguments=json.dumps(block.input)
                    ))
                    
            return Response(
                message=Message(role="assistant", content=content, tool_calls=tool_calls),
                usage={"completion_tokens": response.usage.output_tokens, "prompt_tokens": response.usage.input_tokens} if hasattr(response, "usage") else {}
            )
        except Exception as e:
            if "Authentication" in str(e) or "401" in str(e):
                raise AuthenticationError(str(e)) from e
            raise ProviderError(str(e)) from e

    def generate_stream(self, messages: List[Message], temperature: float = 0.7, max_tokens: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> Iterator[ResponseChunk]:
        raise NotImplementedError("Streaming not yet implemented for AnthropicProvider")

    async def agenerate_stream(self, messages: List[Message], temperature: float = 0.7, max_tokens: Optional[int] = None, tools: Optional[List[Dict[str, Any]]] = None, **kwargs) -> AsyncIterator[ResponseChunk]:
        raise NotImplementedError("Streaming not yet implemented for AnthropicProvider")
