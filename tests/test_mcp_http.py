import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from orkestra.mcp.http_client import MCPHttpToolkit

@pytest.mark.asyncio
async def test_mcp_http_toolkit_lifecycle():
    with patch("orkestra.mcp.http_client.sse_client") as mock_sse_client, \
         patch("orkestra.mcp.http_client.ClientSession") as mock_client_session:
             
        # Mock SSE
        mock_sse_cm = AsyncMock()
        mock_sse_cm.__aenter__.return_value = (AsyncMock(), AsyncMock())
        mock_sse_client.return_value = mock_sse_cm
        
        # Mock Session
        mock_session_inst = AsyncMock()
        mock_session_cm = AsyncMock()
        mock_session_cm.__aenter__.return_value = mock_session_inst
        mock_client_session.return_value = mock_session_cm
        
        # Mock tools
        mock_tool_1 = MagicMock(name="test_tool", description="A test tool", inputSchema={"type": "object", "properties": {}})
        # Overwrite the actual mock name attribute to bypass MagicMock's internal name handling
        mock_tool_1.name = "test_tool"
        
        mock_session_inst.list_tools.return_value = MagicMock(tools=[mock_tool_1])
        
        # Mock tool call response
        mock_session_inst.call_tool.return_value = MagicMock(
            isError=False, 
            content=[MagicMock(type="text", text="Success")]
        )
        
        toolkit = MCPHttpToolkit("http://mock/sse", headers={"Auth": "Key"})
        
        async with toolkit as tools:
            assert len(tools) == 1
            assert tools[0].name == "test_tool"
            assert tools[0].description == "A test tool"
            
            # Execute the tool
            result = await tools[0].arun()
            assert result == "Success"
            
        # Verify initialization and call logic
        mock_session_inst.initialize.assert_awaited_once()
        mock_session_inst.call_tool.assert_awaited_once_with("test_tool", arguments={})
