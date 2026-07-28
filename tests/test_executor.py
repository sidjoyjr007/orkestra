import pytest
import asyncio
import json
from unittest.mock import MagicMock, AsyncMock, patch

from orkestra.core.executor import ToolExecutor
from orkestra.core.messages import Message, ToolCall
from orkestra.events.bus import EventBus
from orkestra.events.base import HumanApprovalProvided, ToolExecutionCompleted
from orkestra.guardrails.base import BaseGuardrail, GuardrailStage, GuardrailAction, GuardrailResult
from orkestra.core.exceptions import WorkflowPausedError

@pytest.fixture
def mock_agent():
    agent = MagicMock()
    agent.name = "TestAgent"
    agent.id = "agent-id"
    agent.session_id = "session-id"
    agent.messages = []
    agent.add_message = MagicMock(side_effect=lambda m: agent.messages.append(m))
    agent.aadd_message = AsyncMock(side_effect=lambda m: agent.messages.append(m))
    agent.guardrails = []
    return agent

@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.apublish = AsyncMock()
    bus.subscribe = MagicMock()
    return bus

def test_executor_init(mock_agent, mock_event_bus):
    executor = ToolExecutor(mock_agent, mock_event_bus)
    assert executor.event_bus == mock_event_bus
    mock_event_bus.subscribe.assert_called_once()
    
def test_on_approval_provided(mock_agent):
    executor = ToolExecutor(mock_agent)
    fut = asyncio.Future()
    executor._pending_approvals["call-1"] = fut
    
    event = HumanApprovalProvided(tool_call_id="call-1", result="Approved")
    executor._on_approval_provided(event)
    
    assert fut.done()
    assert fut.result() == "Approved"

def test_execute_tool_not_found(mock_agent):
    executor = ToolExecutor(mock_agent)
    mock_agent.tools = []
    
    executor.execute([ToolCall(id="1", function_name="missing", function_arguments="")])
    assert len(mock_agent.messages) == 1
    assert "Error: Tool 'missing' not found" in mock_agent.messages[0].content

def test_execute_tool_loop_warning(mock_agent):
    executor = ToolExecutor(mock_agent)
    tool = MagicMock()
    tool.name = "tool"
    tool.requires_approval = False
    mock_agent.tools = [tool]
    
    # 3 historical calls
    call = ToolCall(id="1", function_name="tool", function_arguments="{}")
    msg = Message(role="assistant", content="", tool_calls=[call])
    mock_agent.messages = [msg, msg, msg]
    
    executor.execute([call])
    
    assert len(mock_agent.messages) == 4
    assert "You have executed the tool 'tool' with these exact arguments" in mock_agent.messages[-1].content

def test_execute_sync_success(mock_agent, mock_event_bus):
    tool = MagicMock()
    tool.name = "test_tool"
    tool.requires_approval = False
    tool.max_result_length = None
    tool.run.return_value = "Success"
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent, mock_event_bus)
    executor.execute([ToolCall(id="1", function_name="test_tool", function_arguments='{"arg": "val"}')])
    
    tool.run.assert_called_with(arg="val", _session_id="session-id", _tool_call_id="1", _agent_name="TestAgent")
    assert mock_agent.messages[-1].content == "Success"

def test_execute_sync_exception(mock_agent):
    tool = MagicMock()
    tool.name = "test_tool"
    tool.requires_approval = False
    tool.max_result_length = None
    tool.run.side_effect = Exception("Crash")
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent)
    executor.execute([ToolCall(id="1", function_name="test_tool", function_arguments="")])
    
    assert "Error executing 'test_tool': Crash" in mock_agent.messages[-1].content

def test_execute_sync_workflow_paused(mock_agent):
    tool = MagicMock()
    tool.name = "test_tool"
    tool.requires_approval = True
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent)
    with pytest.raises(WorkflowPausedError):
        executor.execute([ToolCall(id="1", function_name="test_tool", function_arguments="")])

class MockGuardrail(BaseGuardrail):
    def __init__(self, action, modified=""):
        super().__init__(GuardrailStage.ACTION, action)
        self._action = action
        self._modified = modified
    async def aevaluate(self, content, **kwargs):
        passed = self._action not in (GuardrailAction.BLOCK, GuardrailAction.FEEDBACK, GuardrailAction.REDACT)
        return GuardrailResult(passed=passed, action=self._action, message="guardrail message", modified_content=self._modified)

def test_execute_sync_guardrail_block(mock_agent):
    mock_agent.guardrails = [MockGuardrail(GuardrailAction.BLOCK)]
    executor = ToolExecutor(mock_agent)
    executor.execute([ToolCall(id="1", function_name="t", function_arguments="")])
    assert "blocked by guardrail" in mock_agent.messages[-1].content

def test_execute_sync_guardrail_feedback(mock_agent):
    mock_agent.guardrails = [MockGuardrail(GuardrailAction.FEEDBACK)]
    executor = ToolExecutor(mock_agent)
    executor.execute([ToolCall(id="1", function_name="t", function_arguments="")])
    assert "SYSTEM WARNING" in mock_agent.messages[-1].content

def test_execute_sync_guardrail_redact(mock_agent):
    mock_agent.guardrails = [MockGuardrail(GuardrailAction.REDACT, '{"redacted": true}')]
    tool = MagicMock()
    tool.name = "t"
    tool.requires_approval = False
    tool.max_result_length = None
    tool.run.return_value = "Success"
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent)
    executor.execute([ToolCall(id="1", function_name="t", function_arguments="{}")])
    
    tool.run.assert_called_with(redacted=True, _session_id="session-id", _tool_call_id="1", _agent_name="TestAgent")

@pytest.mark.asyncio
async def test_aexecute_async_success(mock_agent, mock_event_bus):
    tool = MagicMock()
    tool.name = "test_tool"
    tool.requires_approval = False
    tool.max_result_length = None
    tool.arun = AsyncMock(return_value="AsyncSuccess")
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent, mock_event_bus)
    await executor.aexecute([ToolCall(id="1", function_name="test_tool", function_arguments="")])
    
    tool.arun.assert_awaited()
    assert mock_agent.messages[-1].content == "AsyncSuccess"

@pytest.mark.asyncio
async def test_aexecute_async_exception(mock_agent):
    tool = MagicMock()
    tool.name = "test_tool"
    tool.requires_approval = False
    tool.max_result_length = None
    tool.arun = AsyncMock(side_effect=Exception("Crash"))
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent)
    await executor.aexecute([ToolCall(id="1", function_name="test_tool", function_arguments="")])
    
    assert "Crash" in mock_agent.messages[-1].content

@pytest.mark.asyncio
async def test_aexecute_hitl_approval_reject(mock_agent):
    tool = MagicMock()
    tool.name = "test_tool"
    tool.requires_approval = True
    tool.max_result_length = None
    tool.arun = AsyncMock()
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent)
    
    # Run aexecute in background
    task = asyncio.create_task(executor.aexecute([ToolCall(id="1", function_name="test_tool", function_arguments="")]))
    
    # Wait for future to be registered
    await asyncio.sleep(0.01)
    
    # Trigger rejection
    executor._on_approval_provided(HumanApprovalProvided(tool_call_id="1", result="[HUMAN REJECTED] Bad"))
    
    await task
    
    tool.arun.assert_not_awaited()
    assert "[HUMAN REJECTED] Bad" in mock_agent.messages[-1].content

def test_execute_sync_truncation(mock_agent):
    tool = MagicMock()
    tool.name = "t"
    tool.requires_approval = False
    tool.run.return_value = "A" * 100
    tool.max_result_length = 50
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent)
    executor.execute([ToolCall(id="1", function_name="t", function_arguments="")])
    
    content = mock_agent.messages[-1].content
    assert len(content) > 50
    assert "[TRUNCATED]" in content

@pytest.mark.asyncio
async def test_aexecute_async_truncation(mock_agent):
    tool = MagicMock()
    tool.name = "t"
    tool.requires_approval = False
    tool.arun = AsyncMock(return_value="A" * 100)
    tool.max_result_length = 50
    mock_agent.tools = [tool]
    
    executor = ToolExecutor(mock_agent)
    await executor.aexecute([ToolCall(id="1", function_name="t", function_arguments="")])
    
    content = mock_agent.messages[-1].content
    assert len(content) > 50
    assert "[TRUNCATED]" in content
