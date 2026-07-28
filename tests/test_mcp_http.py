import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from orkestra.mcp.http_client import MCPHttpToolkit
import httpx
import json

@pytest.mark.asyncio
async def test_mcp_http_toolkit_lifecycle():
    with patch("orkestra.mcp.http_client.httpx.AsyncClient") as mock_client_class:
             
        # Mock Session
        mock_client = MagicMock()
        mock_client.aclose = AsyncMock()
        mock_client_class.return_value = mock_client
        
        # Mock tools endpoint response for stream iteration
        mock_stream_ctx = AsyncMock()
        mock_response = AsyncMock()
        mock_response.status_code = 200
        
        # Create a mock json response
        response_data = {
            "jsonrpc": "2.0",
            "result": {
                "tools": [
                    {
                        "name": "test_tool",
                        "description": "A test tool",
                        "inputSchema": {"type": "object", "properties": {}}
                    }
                ]
            }
        }
        
        # aiter_lines yields lines
        async def mock_aiter_lines():
            yield "event: message"
            yield f"data: {json.dumps(response_data)}"
            
        mock_response.aiter_lines = mock_aiter_lines
        mock_stream_ctx.__aenter__.return_value = mock_response
        mock_client.stream.return_value = mock_stream_ctx
        
        toolkit = MCPHttpToolkit("http://mock/sse", headers={"Auth": "Key"})
        
        tools = await toolkit.load_tools()
        
        assert len(tools) == 1
        assert tools[0].name == "test_tool"
        assert tools[0].description == "A test tool"
        
        # Mock tool call response
        call_response_data = {
            "jsonrpc": "2.0",
            "result": {
                "content": [{"type": "text", "text": "Success"}],
                "isError": False
            }
        }
        
        async def mock_call_aiter_lines():
            yield "event: message"
            yield f"data: {json.dumps(call_response_data)}"
            
        mock_call_response = AsyncMock()
        mock_call_response.status_code = 200
        mock_call_response.aiter_lines = mock_call_aiter_lines
        
        mock_call_stream_ctx = AsyncMock()
        mock_call_stream_ctx.__aenter__.return_value = mock_call_response
        mock_client.stream.return_value = mock_call_stream_ctx
        
        # Execute the tool
        result = await tools[0].arun()
        assert result == "Success"
        
        await toolkit.close()
