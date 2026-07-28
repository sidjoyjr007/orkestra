import pytest
import os
import tempfile
from unittest.mock import MagicMock
from orkestra.core.builtin_tools import (
    read_file_chunk_func,
    get_read_file_chunk_tool,
    get_search_tools_tool
)
from orkestra.core.tools import Tool

def test_read_file_chunk_func():
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a test file
        test_file = os.path.join(tmpdir, "test.txt")
        content = "0123456789abcdefghijklmnopqrstuvwxyz"
        with open(test_file, "w") as f:
            f.write(content)
            
        # Valid read
        res = read_file_chunk_func(test_file, 0, 10, tmpdir)
        assert res == "0123456789"
        
        # Valid read with negative index
        res = read_file_chunk_func(test_file, -26, -16, tmpdir)
        assert res == "abcdefghij"
        
        # Valid read with out of bounds negative index
        res = read_file_chunk_func(test_file, -100, -26, tmpdir)
        assert res == "0123456789"
        
        # Invalid dir
        res = read_file_chunk_func(test_file, 0, 10, "/some/other/dir")
        assert "Permission denied" in res
        
        # File not found
        res = read_file_chunk_func(os.path.join(tmpdir, "missing.txt"), 0, 10, tmpdir)
        assert "File not found" in res
        
        # Invalid indices
        res = read_file_chunk_func(test_file, 10, 5, tmpdir)
        assert "end_char must be greater than start_char" in res
        
        # Exception during read (e.g. read a directory)
        res = read_file_chunk_func(tmpdir, 0, 10, tmpdir)
        assert "Error reading file" in res

def test_get_read_file_chunk_tool():
    tool = get_read_file_chunk_tool("/tmp/artifacts")
    assert tool.name == "read_file_chunk"
    assert "start_char" in tool.schema["function"]["parameters"]["properties"]
    assert tool.requires_approval is False

def test_get_search_tools_tool_no_results():
    mock_agent = MagicMock()
    mock_agent.tool_registry.search.return_value = []
    
    tool = get_search_tools_tool(mock_agent)
    res = tool.func(query="test")
    assert "No matching tools found" in res

def test_get_search_tools_tool_with_results():
    mock_agent = MagicMock()
    
    tool1 = Tool(name="tool1", description="desc1", func=lambda: None, schema={})
    tool2 = Tool(name="tool2", description="desc2", func=lambda: None, schema={})
    
    mock_agent.tool_registry.search.return_value = [tool1, tool2]
    mock_agent.tools = [tool1] # tool1 is already there
    
    tool = get_search_tools_tool(mock_agent)
    res = tool.func(query="test")
    
    assert "Found the following tools" in res
    assert "tool1" in res
    assert "tool2" in res
    
    # Check that tool2 was injected
    assert len(mock_agent.tools) == 2
    assert mock_agent.tools[1].name == "tool2"
