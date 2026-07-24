import os
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
from google import genai
from google.genai import types, errors
from orkestra.core.messages import Message, Response, ResponseChunk, ToolCall
from orkestra.providers.base import BaseProvider
from orkestra.core.exceptions import (
    AuthenticationError, RateLimitError, ProviderError, ContextWindowExceededError
)
import functools
import asyncio
from tenacity import retry, retry_if_exception_type, wait_exponential, stop_after_attempt
from orkestra.events.base import ProviderRetrying


def _publish_retry_event(retry_state):
    # Try to extract the provider instance from args to access event_bus
    if retry_state.args and hasattr(retry_state.args[0], 'event_bus') and retry_state.args[0].event_bus:
        provider = retry_state.args[0]
        event = ProviderRetrying(
            provider_name=provider.__class__.__name__,
            attempt_number=retry_state.attempt_number,
            wait_time_seconds=retry_state.idle_for,
            error=str(retry_state.outcome.exception())
        )
        # Using synchronous publish since before_sleep is always called synchronously by tenacity
        provider.event_bus.publish(event)
    else:
        # Fallback to standard logging if no event bus is configured
        print(
            f"WARNING: Retrying LLM call in {retry_state.idle_for} seconds as it raised {str(retry_state.outcome.exception())}"
        )

with_retry = retry(
    retry=retry_if_exception_type((RateLimitError, ProviderError)),
    wait=wait_exponential(multiplier=1, min=2, max=60),
    stop=stop_after_attempt(3),
    before_sleep=_publish_retry_event,
    reraise=True
)

def _handle_gemini_errors(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except errors.APIError as e:
            err_str = str(e).lower()
            if "401" in err_str or "unauthenticated" in err_str or "api key not valid" in err_str:
                raise AuthenticationError(str(e)) from e
            if "429" in err_str or "quota" in err_str or "rate" in err_str:
                raise RateLimitError(str(e)) from e
            if "invalid argument" in err_str or "400" in err_str:
                raise ProviderError(str(e)) from e
            raise ProviderError(str(e)) from e
        except Exception as e:
            raise ProviderError(str(e)) from e
    
    @functools.wraps(func)
    async def awrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except errors.APIError as e:
            err_str = str(e).lower()
            if "401" in err_str or "unauthenticated" in err_str or "api key not valid" in err_str:
                raise AuthenticationError(str(e)) from e
            if "429" in err_str or "quota" in err_str or "rate" in err_str:
                raise RateLimitError(str(e)) from e
            if "invalid argument" in err_str or "400" in err_str:
                raise ProviderError(str(e)) from e
            raise ProviderError(str(e)) from e
        except Exception as e:
            raise ProviderError(str(e)) from e
            
    if asyncio.iscoroutinefunction(func):
        return awrapper
    return wrapper

class GeminiProvider(BaseProvider):
    """Google Gemini API provider implementation."""

    def __init__(self, model_name: str = "gemini-2.5-pro", api_key: Optional[str] = None, event_bus: Optional[Any] = None, **kwargs):
        super().__init__(model_name, api_key, event_bus, **kwargs)
        self.client = genai.Client(api_key=self.api_key or os.environ.get("GEMINI_API_KEY"))

    def _format_messages(self, messages: List[Message]) -> List[types.Content]:
        formatted = []
        for msg in messages:
            if msg.role == "system":
                continue
            
            role = "model" if msg.role == "assistant" else "user"
            
            parts = []
            if msg.content:
                parts.append(types.Part.from_text(text=msg.content))
            
            if msg.tool_calls:
                for tc in msg.tool_calls:
                    import json
                    parts.append(types.Part.from_function_call(
                        name=tc.function_name,
                        args=json.loads(tc.function_arguments) if tc.function_arguments else {}
                    ))
                    
            if msg.role == "tool":
                parts.append(types.Part.from_function_response(
                    name=msg.name or "unknown",
                    response={"result": msg.content}
                ))

            if parts:
                formatted.append(types.Content(role=role, parts=parts))
                
        return formatted

    def _convert_tools_to_gemini(self, tools: List[Dict[str, Any]]) -> List[types.Tool]:
        """Convert standard JSON schema tools to Gemini Tool objects."""
        gemini_funcs = []
        for t in tools:
            if "type" in t and t["type"] == "function":
                func = t["function"]
                # Convert the JSON schema to Gemini's Schema object
                properties = {}
                for k, v in func.get("parameters", {}).get("properties", {}).items():
                    properties[k] = types.Schema(
                        type=types.Type.STRING if v.get("type") == "string" else types.Type.INTEGER,
                        description=v.get("description", "")
                    )
                
                schema = types.Schema(
                    type=types.Type.OBJECT,
                    properties=properties,
                    required=func.get("parameters", {}).get("required", [])
                )
                
                gemini_funcs.append(
                    types.FunctionDeclaration(
                        name=func["name"],
                        description=func["description"],
                        parameters=schema
                    )
                )
        if not gemini_funcs:
            return None
        return [types.Tool(function_declarations=gemini_funcs)]
        
    def _extract_system_instruction(self, messages: List[Message]) -> Optional[str]:
        system_msgs = [m.content for m in messages if m.role == "system" and m.content]
        return "\n".join(system_msgs) if system_msgs else None

    @with_retry
    @_handle_gemini_errors
    def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> Response:
        formatted_messages = self._format_messages(messages)
        system_instruction = self._extract_system_instruction(messages)
        
        gemini_tools = None
        if tools:
            gemini_tools = self._convert_tools_to_gemini(tools)
            
        response = self.client.models.generate_content(
            model=self.model_name,
            contents=formatted_messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
                tools=gemini_tools,
                **kwargs
            )
        )
        
        tool_calls = None
        if response.function_calls:
            import json
            tool_calls = [
                ToolCall(
                    id=f"call_{i}",
                    function_name=fc.name,
                    function_arguments=json.dumps(fc.args)
                )
                for i, fc in enumerate(response.function_calls)
            ]
            
        content = None
        if response.candidates and response.candidates[0].content:
            parts = []
            for part in response.candidates[0].content.parts:
                if getattr(part, "text", None):
                    parts.append(part.text)
            if parts:
                content = "".join(parts)
            
        message = Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls
        )
        
        usage = {}
        if response.usage_metadata:
            usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count or 0,
                "completion_tokens": response.usage_metadata.candidates_token_count or 0,
                "total_tokens": response.usage_metadata.total_token_count or 0
            }

        return Response(
            message=message,
            finish_reason=response.candidates[0].finish_reason.name if response.candidates and hasattr(response.candidates[0].finish_reason, "name") else None,
            usage=usage
        )

    @with_retry
    @_handle_gemini_errors
    def generate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> Iterator[ResponseChunk]:
        formatted_messages = self._format_messages(messages)
        system_instruction = self._extract_system_instruction(messages)
        
        gemini_tools = None
        if tools:
            gemini_tools = self._convert_tools_to_gemini(tools)
            
        stream = self.client.models.generate_content_stream(
            model=self.model_name,
            contents=formatted_messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
                tools=gemini_tools,
                **kwargs
            )
        )
        
        for chunk in stream:
            tool_calls = None
            if chunk.function_calls:
                import json
                tool_calls = [
                    ToolCall(
                        id=f"call_stream_{fc.name}",
                        function_name=fc.name,
                        function_arguments=json.dumps(fc.args)
                    )
                    for fc in chunk.function_calls
                ]

            yield ResponseChunk(
                content=chunk.text,
                tool_calls=tool_calls,
                finish_reason=chunk.candidates[0].finish_reason.name if chunk.candidates and hasattr(chunk.candidates[0].finish_reason, "name") else None
            )

    @with_retry
    @_handle_gemini_errors
    async def agenerate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> Response:
        formatted_messages = self._format_messages(messages)
        system_instruction = self._extract_system_instruction(messages)
        
        gemini_tools = None
        if tools:
            gemini_tools = self._convert_tools_to_gemini(tools)
            
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=formatted_messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
                tools=gemini_tools,
                **kwargs
            )
        )
        
        tool_calls = None
        if response.function_calls:
            import json
            tool_calls = [
                ToolCall(
                    id=f"call_{i}",
                    function_name=fc.name,
                    function_arguments=json.dumps(fc.args)
                )
                for i, fc in enumerate(response.function_calls)
            ]
            
        content = None
        if response.candidates and response.candidates[0].content:
            parts = []
            for part in response.candidates[0].content.parts:
                if getattr(part, "text", None):
                    parts.append(part.text)
            if parts:
                content = "".join(parts)
                
        message = Message(
            role="assistant",
            content=content,
            tool_calls=tool_calls
        )
        
        usage = {}
        if response.usage_metadata:
            usage = {
                "prompt_tokens": response.usage_metadata.prompt_token_count,
                "completion_tokens": response.usage_metadata.candidates_token_count,
                "total_tokens": response.usage_metadata.total_token_count
            }

        return Response(
            message=message,
            finish_reason=response.candidates[0].finish_reason.name if response.candidates and hasattr(response.candidates[0].finish_reason, "name") else None,
            usage=usage
        )

    @with_retry
    @_handle_gemini_errors
    async def agenerate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Any]] = None,
        **kwargs
    ) -> AsyncIterator[ResponseChunk]:
        formatted_messages = self._format_messages(messages)
        system_instruction = self._extract_system_instruction(messages)
        
        gemini_tools = None
        if tools:
            gemini_tools = self._convert_tools_to_gemini(tools)
            
        stream = await self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=formatted_messages,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=temperature,
                max_output_tokens=max_tokens,
                tools=gemini_tools,
                **kwargs
            )
        )
        
        async for chunk in stream:
            tool_calls = None
            if chunk.function_calls:
                import json
                tool_calls = [
                    ToolCall(
                        id=f"call_stream_{fc.name}",
                        function_name=fc.name,
                        function_arguments=json.dumps(fc.args)
                    )
                    for fc in chunk.function_calls
                ]

            yield ResponseChunk(
                content=chunk.text,
                tool_calls=tool_calls,
                finish_reason=chunk.candidates[0].finish_reason.name if chunk.candidates and hasattr(chunk.candidates[0].finish_reason, "name") else None
            )

