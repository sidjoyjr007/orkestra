import pytest
from unittest.mock import patch, MagicMock
import json

from orkestra.core.tool_registry import ToolRegistry
from orkestra.core.messages import Message
from orkestra.core.tools import Tool, HostTool
from orkestra.mcp.http_client import MCPTool

@pytest.fixture
def mock_chroma():
    with patch("orkestra.core.tool_registry.chromadb.HttpClient") as mock_client:
        mock_collection = MagicMock()
        mock_client.return_value.get_collection.return_value = mock_collection
        yield mock_client, mock_collection

def test_tool_registry_initialization(mock_chroma):
    mock_client, mock_collection = mock_chroma
    
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    assert registry.collection == mock_collection
    
    # Test missing collection
    registry.collection = None
    assert registry.search("query") == []
    
def test_tool_registry_init_failure():
    with patch("orkestra.core.tool_registry.chromadb.HttpClient", side_effect=Exception("Failed")):
        registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
        assert registry.collection is None

def test_search_success(mock_chroma):
    _, mock_collection = mock_chroma
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    
    # Mock search results with 1 valid matching tool, 1 below threshold, 1 invalid schema
    valid_schema = json.dumps({"function": {"name": "valid_tool", "description": "valid desc"}})
    invalid_schema = "invalid json"
    
    # distance 0.1 -> similarity 1.0 - (0.1/2) = 0.95 (above 0.4)
    # distance 1.5 -> similarity 1.0 - (1.5/2) = 0.25 (below 0.4)
    mock_collection.query.return_value = {
        "documents": [["doc1", "doc2", "doc3"]],
        "distances": [[0.1, 1.5, 0.1]],
        "metadatas": [
            [
                {"schema": valid_schema, "type": "local", "code": "def valid_tool(): pass"},
                {"schema": valid_schema, "type": "local"}, # Below threshold
                {"schema": invalid_schema, "type": "local"} # Invalid schema
            ]
        ]
    }
    
    tools = registry.search("find valid tool", threshold=0.4)
    
    assert len(tools) == 1
    assert tools[0].name == "valid_tool"
    assert tools[0].description == "valid desc"
    
def test_search_empty_results(mock_chroma):
    _, mock_collection = mock_chroma
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    
    mock_collection.query.return_value = {"documents": []}
    assert registry.search("query") == []

def test_search_exception(mock_chroma):
    _, mock_collection = mock_chroma
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    
    mock_collection.query.side_effect = Exception("DB error")
    assert registry.search("query") == []
    
def test_reconstruct_mcp_tool(mock_chroma):
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    schema = json.dumps({"function": {"name": "mcp_tool"}})
    
    tool = registry._reconstruct_tool({
        "schema": schema,
        "type": "mcp",
        "mcp_url": "http://mcp:8000"
    })
    
    assert isinstance(tool, MCPTool)
    assert tool.name == "mcp_tool"
    
    # Test missing mcp_url
    invalid_mcp = registry._reconstruct_tool({"schema": schema, "type": "mcp"})
    assert invalid_mcp is None

def test_reconstruct_local_tool_with_code(mock_chroma):
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    schema = json.dumps({"function": {"name": "calc"}})
    
    code = "def calc(a, b): return a + b"
    tool = registry._reconstruct_tool({
        "schema": schema,
        "type": "local",
        "code": code
    })
    
    assert isinstance(tool, Tool)
    assert tool.name == "calc"
    assert tool.func(a=1, b=2) == 3
    assert getattr(tool.func, "__source_code__") == code

def test_reconstruct_local_tool_missing_code(mock_chroma):
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    schema = json.dumps({"function": {"name": "calc"}})
    
    tool = registry._reconstruct_tool({
        "schema": schema,
        "type": "local"
    })
    
    with pytest.raises(NotImplementedError):
        tool.func()
        
def test_reconstruct_local_tool_invalid_code(mock_chroma):
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    schema = json.dumps({"function": {"name": "calc"}})
    
    # Missing function definition
    tool = registry._reconstruct_tool({
        "schema": schema,
        "type": "local",
        "code": "x = 1"
    })
    
    with pytest.raises(NotImplementedError):
        tool.func()

def test_reconstruct_host_tool(mock_chroma):
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    schema = json.dumps({"function": {"name": "host_func"}})
    
    tool = registry._reconstruct_tool({
        "schema": schema,
        "type": "host_tool",
        "code": "def host_func(): pass"
    })
    
    assert isinstance(tool, HostTool)
    assert tool.name == "host_func"

def test_inject_semantic_tools(mock_chroma):
    registry = ToolRegistry(url="http://localhost:8000", agent_id="agent1")
    
    mock_agent = MagicMock()
    mock_agent.id = "agent1"
    mock_agent.messages = [
        Message(role="user", content="I need a tool")
    ]
    
    existing_tool = Tool(name="existing", description="e", func=lambda: None, schema={})
    mock_agent.tools = [existing_tool]
    
    new_tool = Tool(name="new_tool", description="n", func=lambda: None, schema={})
    with patch.object(registry, "search", return_value=[existing_tool, new_tool]) as mock_search:
        registry.inject_semantic_tools(mock_agent)
        mock_search.assert_called_with("I need a tool")
        
    assert len(mock_agent.tools) == 2
    assert mock_agent.tools[1].name == "new_tool"
