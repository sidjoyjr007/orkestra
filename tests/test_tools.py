import pytest
import asyncio
import json
import subprocess
from unittest.mock import patch, MagicMock

from orkestra.core.tools import Tool, HostTool
from orkestra.core.exceptions import WorkflowPausedError

def dummy_func(x):
    return x * 2
    
async def async_dummy_func(x):
    return x * 2

def test_tool_initialization():
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={}, dependencies=["requests"])
    assert tool.name == "calc"
    assert tool.description == "calc desc"
    assert tool.dependencies == ["requests"]
    assert "orkestra-tool" in tool.image_tag

@patch("orkestra.core.tools.subprocess.run")
def test_tool_ensure_image_cache_hit(mock_run):
    # Mock 'docker image inspect' returning 0 (success)
    mock_run.return_value = MagicMock(returncode=0)
    
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={}, dependencies=["requests"])
    tool._ensure_image()
    
    mock_run.assert_called_once()
    assert "inspect" in mock_run.call_args[0][0]

@patch("orkestra.core.tools.subprocess.run")
def test_tool_ensure_image_cache_miss(mock_run):
    # Mock inspect fail, then build success
    mock_run.side_effect = [
        MagicMock(returncode=1),
        MagicMock(returncode=0)
    ]
    
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={}, dependencies=["requests"])
    tool._ensure_image()
    
    assert mock_run.call_count == 2
    assert "build" in mock_run.call_args_list[1][0][0]

@patch("orkestra.core.tools.subprocess.run")
def test_tool_execute_in_docker_success(mock_run):
    # Mock ensure_image
    mock_run.side_effect = [
        MagicMock(returncode=0), # inspect
        MagicMock(returncode=0, stdout=json.dumps({"status": "success", "result": 10})) # run
    ]
    
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={})
    res = tool._execute_in_docker({"x": 5})
    
    assert res == "10"

@patch("orkestra.core.tools.subprocess.run")
def test_tool_execute_in_docker_timeout(mock_run):
    # Mock ensure_image
    def side_effect(*args, **kwargs):
        if "inspect" in args[0]:
            return MagicMock(returncode=0)
        raise subprocess.TimeoutExpired(cmd="docker", timeout=60)
        
    mock_run.side_effect = side_effect
    
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={})
    res = tool._execute_in_docker({"x": 5})
    
    assert "timed out" in json.loads(res)["error"]

@patch("orkestra.core.tools.subprocess.run")
def test_tool_execute_in_docker_process_fail(mock_run):
    mock_run.side_effect = [
        MagicMock(returncode=0), # inspect
        MagicMock(returncode=1, stderr=b"Docker error") # run
    ]
    
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={})
    res = tool._execute_in_docker({"x": 5})
    
    assert "Tool execution failed: b'Docker error'" in json.loads(res)["error"]

@patch("orkestra.core.tools.subprocess.run")
def test_tool_execute_in_docker_tool_error(mock_run):
    mock_run.side_effect = [
        MagicMock(returncode=0), # inspect
        MagicMock(returncode=0, stdout=json.dumps({"status": "error", "error": "Zero division"})) # run
    ]
    
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={})
    res = tool._execute_in_docker({"x": 5})
    
    assert json.loads(res)["error"] == "Zero division"

@patch("orkestra.core.tools.subprocess.run")
def test_tool_execute_in_docker_invalid_json(mock_run):
    mock_run.side_effect = [
        MagicMock(returncode=0), # inspect
        MagicMock(returncode=0, stdout="not json") # run
    ]
    
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={})
    res = tool._execute_in_docker({"x": 5})
    
    assert "Failed to parse tool output" in json.loads(res)["error"]

@patch("orkestra.core.tools.Tool._execute_in_docker")
def test_tool_run_sync(mock_exec):
    mock_exec.return_value = "res"
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={})
    assert tool.run(x=5) == "res"
    mock_exec.assert_called_with({"x": 5})

@pytest.mark.asyncio
@patch("orkestra.core.tools.Tool._execute_in_docker")
async def test_tool_arun_async(mock_exec):
    mock_exec.return_value = "res"
    tool = Tool(name="calc", description="calc desc", func=dummy_func, schema={})
    assert await tool.arun(x=5) == "res"
    mock_exec.assert_called_with({"x": 5})

@pytest.mark.asyncio
async def test_host_tool_arun_sync():
    tool = HostTool(name="calc", description="calc desc", func=dummy_func, schema={})
    res = await tool.arun(x=5, _internal="ignore")
    assert res == 10

@pytest.mark.asyncio
async def test_host_tool_arun_async():
    tool = HostTool(name="calc", description="calc desc", func=async_dummy_func, schema={})
    res = await tool.arun(x=5)
    assert res == 10

@pytest.mark.asyncio
async def test_host_tool_arun_error():
    def fail_func():
        raise ValueError("Oops")
    tool = HostTool(name="calc", description="calc desc", func=fail_func, schema={})
    res = await tool.arun()
    assert "Oops" in res

@pytest.mark.asyncio
async def test_host_tool_arun_workflow_paused():
    def pause_func():
        raise WorkflowPausedError("Paused")
    tool = HostTool(name="calc", description="calc desc", func=pause_func, schema={})
    with pytest.raises(WorkflowPausedError):
        await tool.arun()

def test_tool_execute_in_docker_source_code_attr():
    # Test when function has __source_code__ attached
    def my_func(): pass
    my_func.__source_code__ = "def my_func(): return 1"
    
    tool = Tool(name="calc", description="calc desc", func=my_func, schema={})
    
    with patch("orkestra.core.tools.subprocess.run") as mock_run:
        mock_run.side_effect = [
            MagicMock(returncode=0), # inspect
            MagicMock(returncode=0, stdout=json.dumps({"status": "success", "result": 1})) # run
        ]
        res = tool._execute_in_docker({})
        assert res == "1"
        
        script = mock_run.call_args_list[1][1]["input"]
        assert "def my_func(): return 1" in script

def test_tool_execute_in_docker_source_code_fail():
    # Test when inspect.getsource fails (e.g. builtins)
    tool = Tool(name="calc", description="calc desc", func=print, schema={})
    res = tool._execute_in_docker({})
    assert "Could not extract source code" in json.loads(res)["error"]
