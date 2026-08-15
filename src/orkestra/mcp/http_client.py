import json
import logging
import uuid
from typing import List, Dict, Optional, Any
from contextlib import AsyncExitStack

from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from orkestra.core.tools import Tool
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession

def _resolve_docker_host(url: str) -> str:
    import os, re
    if os.path.exists("/.dockerenv"):
        url = re.sub(r'://localhost\b', '://host.docker.internal', url)
        url = re.sub(r'://127\.0\.0\.1\b', '://host.docker.internal', url)
    return url

logger = logging.getLogger(__name__)

class MCPTool(Tool):
    """A proxy tool that executes remotely on an MCP server using the official standard."""
    def __init__(self, name: str, description: str, schema: Dict[str, Any], session: Optional[ClientSession] = None, url: str = "", headers: Optional[Dict[str, str]] = None, **kwargs):
        super().__init__(name, description, lambda **kwargs: None, schema)
        self._session = session
        self._mcp_tool_name = name
        # Backwards compatibility for state.py serialization
        self._url = _resolve_docker_host(url)
        self._headers = headers or {}
        if not self._headers.get("Accept"):
            self._headers["Accept"] = "text/event-stream, application/json"

    def run(self, **kwargs) -> str:
        raise NotImplementedError("MCP Tools must be executed asynchronously via arun()")
        
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True
    )
    async def arun(self, **kwargs) -> str:
        # Strip internal Orkestra kwargs (like _session_id, _tool_call_id)
        clean_kwargs = {k: v for k, v in kwargs.items() if not k.startswith("_")}
        
        logger.debug(f"Executing MCP tool '{self._mcp_tool_name}' with args: {clean_kwargs}")
        
        try:
            if self._session:
                try:
                    result = await self._session.call_tool(self._mcp_tool_name, arguments=clean_kwargs)
                except Exception as e:
                    logger.warning(f"MCP Session failed ({e}). Falling back to fresh connection.")
                    self._session = None

            if not self._session:
                logger.error(f"Connecting fresh to MCP Tool Server: {self._url}")
                async with AsyncExitStack() as stack:
                    sse = await stack.enter_async_context(sse_client(url=self._url, headers=self._headers, timeout=300))
                    session = await stack.enter_async_context(ClientSession(sse[0], sse[1]))
                    await session.initialize()
                    result = await session.call_tool(self._mcp_tool_name, arguments=clean_kwargs)

            
            if getattr(result, "isError", False):
                return f"Error: {result.content}"
                
            output_text = []
            for content in result.content:
                if content.type == "text":
                    output_text.append(content.text)
                else:
                    output_text.append(f"[{content.type} content]")
                    
            return "\n".join(output_text)
        except Exception as e:
            import traceback
            tb = "".join(traceback.format_exception(type(e), e, e.__traceback__))
            logger.error(f"MCP Tool Exception:\n{tb}")
            
            if isinstance(e, BaseExceptionGroup):
                sub_errs = ", ".join(repr(err) for err in e.exceptions)
                raise RuntimeError(f"Tool execution failed: {e} ({sub_errs})")
            raise RuntimeError(f"Tool execution failed: {e}")

class MCPHttpToolkit:
    """
    Connects to a remote MCP server using the official MCP standard (SSE transport).
    """
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = _resolve_docker_host(url)
        self.headers = headers or {}
        # Required for standard SSE responses
        self.headers["Accept"] = "text/event-stream, application/json"
        
        self._exit_stack = AsyncExitStack()
        self._session = None

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        reraise=True
    )
    async def load_tools(self) -> List[Tool]:
        """Fetches the tools from the MCP server and returns them as native Orkestra tools."""
        logger.info(f"Connecting to MCP endpoint: {self.url}")
        
        try:
            # Enter SSE context
            sse = await self._exit_stack.enter_async_context(sse_client(url=self.url, headers=self.headers, timeout=300))
            
            # Enter Session context
            self._session = await self._exit_stack.enter_async_context(ClientSession(sse[0], sse[1]))
            
            # Initialize connection
            await self._session.initialize()
            
            # List tools
            tools_response = await self._session.list_tools()
            
            orkestra_tools = []
            
            def _fix_schema(s: dict):
                import copy
                s = copy.deepcopy(s)
                def traverse(obj):
                    if isinstance(obj, dict):
                        type_val = obj.get("type")
                        is_array = (type_val == "array") or (isinstance(type_val, list) and "array" in type_val)
                        is_object = (type_val == "object") or (isinstance(type_val, list) and "object" in type_val)
                        
                        if is_array:
                            if "items" not in obj or not isinstance(obj["items"], dict):
                                obj["items"] = {"type": "string"}
                            elif "type" not in obj["items"] and "anyOf" not in obj["items"]:
                                obj["items"]["type"] = "string"
                                
                        if is_object and "properties" not in obj:
                            obj["properties"] = {}
                            
                        for k, v in obj.items():
                            traverse(v)
                    elif isinstance(obj, list):
                        for item in obj:
                            traverse(item)
                traverse(s)
                return s

            for t in tools_response.tools:
                fixed_input_schema = _fix_schema(t.inputSchema)
                # Wrap the MCP input schema in an OpenAI-compatible function schema
                schema = {
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": fixed_input_schema
                    }
                }
                
                orkestra_tools.append(MCPTool(
                    name=t.name,
                    description=t.description or "",
                    schema=schema,
                    session=self._session,
                    url=self.url
                ))
                
            logger.info(f"Successfully mapped {len(orkestra_tools)} MCP tools.")
            return orkestra_tools
            
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            raise

    async def close(self):
        """Closes the underlying HTTP client and MCP session."""
        try:
            await self._exit_stack.aclose()
            logger.info("MCP connection closed.")
        except Exception as e:
            logger.error(f"Error during MCP connection teardown: {e}")
