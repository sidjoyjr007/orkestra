import pytest
from unittest.mock import MagicMock
from orkestra.core.state import AgentStateSerializer
from orkestra.core.tools import Tool

def test_agent_state_serializer_to_dict():
    mock_agent = MagicMock()
    mock_agent.id = "agent-123"
    mock_agent.name = "TestAgent"
    mock_agent.session_id = "session-123"
    
    # Native tool
    native_tool = Tool(name="native_tool", description="A native tool", func=lambda: None, schema={})
    
    # MCP tool mock
    mcp_tool = MagicMock()
    mcp_tool.name = "mcp_tool"
    mcp_tool._mcp_tool_name = "mcp_tool" # Flag indicating MCP tool
    mcp_tool._url = "http://localhost:8000"
    mcp_tool.schema = {"function": {"name": "mcp_tool", "description": "MCP desc"}}
    mcp_tool._headers = {"Authorization": "Bearer token"}
    
    mock_agent.tools = [native_tool, mcp_tool]
    
    state = AgentStateSerializer.to_dict(mock_agent)
    
    assert state["id"] == "agent-123"
    assert state["name"] == "TestAgent"
    assert state["session_id"] == "session-123"
    
    tools_state = state["tools"]
    assert len(tools_state) == 2
    
    assert tools_state[0]["type"] == "native"
    assert tools_state[0]["name"] == "native_tool"
    
    assert tools_state[1]["type"] == "mcp"
    assert tools_state[1]["name"] == "mcp_tool"
    assert tools_state[1]["mcp_url"] == "http://localhost:8000"
    assert tools_state[1]["schema"] == mcp_tool.schema
    assert tools_state[1]["headers"] == {"Authorization": "Bearer token"}

def test_agent_state_serializer_load_state():
    mock_agent = MagicMock()
    mock_agent.id = "old-agent"
    mock_agent.name = "OldAgent"
    mock_agent.tools = []
    
    base_tools = [
        Tool(name="native_tool", description="A native tool", func=lambda: None, schema={})
    ]
    
    state = {
        "id": "agent-123",
        "name": "TestAgent",
        "session_id": "session-123",
        "tools": [
            {"type": "native", "name": "native_tool"},
            {"type": "native", "name": "missing_native"}, # Should be ignored if not in base_tools
            {
                "type": "mcp", 
                "name": "mcp_tool", 
                "schema": {"function": {"description": "mcp desc"}},
                "mcp_url": "http://localhost:8000",
                "headers": {"Authorization": "Bearer token"}
            }
        ]
    }
    
    AgentStateSerializer.load_state(mock_agent, state, base_tools)
    
    assert mock_agent.id == "agent-123"
    assert mock_agent.name == "TestAgent"
    
    assert len(mock_agent.tools) == 2
    assert mock_agent.tools[0].name == "native_tool"
    
    mcp_loaded = mock_agent.tools[1]
    assert mcp_loaded.name == "mcp_tool"
    assert mcp_loaded.description == "mcp desc"
    assert mcp_loaded._url == "http://localhost:8000"
    assert mcp_loaded._headers == {"Authorization": "Bearer token"}

def test_agent_state_serializer_load_state_empty():
    mock_agent = MagicMock()
    mock_agent.id = "old-agent"
    AgentStateSerializer.load_state(mock_agent, None, [])
    assert mock_agent.id == "old-agent"
