import json
import logging
import uuid
from typing import List, Dict, Optional, Any
import httpx
from tenacity import retry, wait_exponential, stop_after_attempt, retry_if_exception_type

from orkestra.core.tools import Tool

logger = logging.getLogger(__name__)

class MCPTool(Tool):
    """A proxy tool that executes remotely on an MCP StreamableHttp server."""
    def __init__(self, name: str, description: str, schema: Dict[str, Any], url: str, headers: Dict[str, str], client: httpx.AsyncClient):
        super().__init__(name, description, lambda **kwargs: None, schema)
        self._url = url
        self._headers = headers
        self._client = client
        self._mcp_tool_name = name

    def run(self, **kwargs) -> str:
        raise NotImplementedError("MCP Tools must be executed asynchronously via arun()")
        
    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, RuntimeError)),
        reraise=True
    )
    async def arun(self, **kwargs) -> str:
        logger.debug(f"Executing MCP tool '{self._mcp_tool_name}' with args: {kwargs}")
        
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {
                "name": self._mcp_tool_name,
                "arguments": kwargs
            },
            "id": str(uuid.uuid4())
        }
        
        async with self._client.stream("POST", self._url, headers=self._headers, json=request_data) as response:
            if response.status_code != 200:
                raise RuntimeError(f"Server returned status {response.status_code}")
                
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    response_json = json.loads(line[6:])
                    if "error" in response_json:
                        raise RuntimeError(f"Tool returned error: {response_json['error']}")
                        
                    result_data = response_json.get("result", {})
                    if result_data.get("isError"):
                        raise RuntimeError(f"Tool execution failed: {result_data}")
                        
                    output_text = []
                    for content in result_data.get("content", []):
                        if content.get("type") == "text":
                            output_text.append(content.get("text", ""))
                        else:
                            output_text.append(f"[{content.get('type')} content]")
                            
                    return "\n".join(output_text)
                    
        raise RuntimeError("No message received from MCP server.")

class MCPHttpToolkit:
    """
    Connects to a remote MCP server using the modern StreamableHttp protocol over POST.
    """
    def __init__(self, url: str, headers: Optional[Dict[str, str]] = None):
        self.url = url
        self.headers = headers or {}
        # Required for StreamableHttp SSE responses
        self.headers["Accept"] = "text/event-stream, application/json"
        self._client = httpx.AsyncClient(timeout=30.0)

    @retry(
        wait=wait_exponential(multiplier=1, min=2, max=10),
        stop=stop_after_attempt(3),
        retry=retry_if_exception_type((httpx.RequestError, RuntimeError)),
        reraise=True
    )
    async def load_tools(self) -> List[Tool]:
        """Fetches the tools from the MCP server and returns them as native Orkestra tools."""
        logger.info(f"Connecting to MCP endpoint: {self.url}")
        
        request_data = {
            "jsonrpc": "2.0",
            "method": "tools/list",
            "id": str(uuid.uuid4())
        }
        
        try:
            async with self._client.stream("POST", self.url, headers=self.headers, json=request_data) as response:
                if response.status_code != 200:
                    error_body = await response.aread()
                    raise RuntimeError(f"Failed to list tools: HTTP {response.status_code} {error_body.decode(errors='ignore')}")
                    
                async for line in response.aiter_lines():
                    if line.startswith("data: "):
                        response_json = json.loads(line[6:])
                        if "error" in response_json:
                            raise RuntimeError(f"Failed to list tools: {response_json['error']}")
                            
                        tools_list = response_json.get("result", {}).get("tools", [])
                        orkestra_tools = []
                        
                        for t in tools_list:
                            schema = {
                                "type": "function",
                                "function": {
                                    "name": t["name"],
                                    "description": t.get("description", ""),
                                    "parameters": t.get("inputSchema", {})
                                }
                            }
                            
                            orkestra_tools.append(MCPTool(
                                name=t["name"],
                                description=t.get("description", ""),
                                schema=schema,
                                url=self.url,
                                headers=self.headers,
                                client=self._client
                            ))
                            
                        logger.info(f"Successfully mapped {len(orkestra_tools)} MCP tools.")
                        return orkestra_tools
                        
            raise RuntimeError("Failed to read tool list: no 'data:' event received from MCP server.")
        except Exception as e:
            logger.error(f"Error connecting to MCP server: {e}")
            raise

    async def close(self):
        """Closes the underlying HTTP client."""
        if self._client:
            await self._client.aclose()
        logger.info("MCP connection closed.")
