import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch

from orkestra.core.agent import Agent
from orkestra.core.messages import Message, Response, ToolCall
from orkestra.core.tools import Tool
from orkestra.guardrails.base import BaseGuardrail, GuardrailStage, GuardrailAction, GuardrailResult

@pytest.fixture
def mock_provider():
    provider = MagicMock()
    provider.agenerate = AsyncMock()
    provider.generate = MagicMock()
    provider.generate_stream = MagicMock()
    provider.agenerate_stream = MagicMock()
    provider.event_bus = None  # Prevent falling back to MagicMock
    return provider

@pytest.fixture
def mock_memory():
    memory = MagicMock()
    memory.aadd_message = AsyncMock()
    memory.add_message = MagicMock()
    memory.get_messages = MagicMock(return_value=None)
    return memory

@pytest.fixture
def mock_workspace():
    workspace = MagicMock()
    workspace.aget_active_plan = AsyncMock(return_value=None)
    return workspace

@pytest.fixture
def mock_event_bus():
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.apublish = AsyncMock()
    return bus

@pytest.fixture
def mock_compaction():
    compaction = MagicMock()
    compaction.aprocess = AsyncMock(side_effect=lambda msgs, sys_p, mem, sid: [Message(role="system", content=sys_p)] + msgs)
    return compaction

def test_agent_init_with_workspace(mock_provider, mock_workspace):
    # Should inject planning tools
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, workspace=mock_workspace)
    assert len(agent.tools) > 0
    assert any(t.name == "create_plan" for t in agent.tools)

def test_agent_init_with_memory_and_messages(mock_provider, mock_memory):
    # Test setting initial messages to memory
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, memory=mock_memory, messages=[Message(role="user", content="hi")])
    assert len(agent.messages) == 1
    mock_memory.add_message.assert_called_once()

def test_approve_reject_tools(mock_provider):
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider)
    
    agent.approve_tool("call1", "tool1", "result")
    assert agent.messages[-1].role == "tool"
    assert agent.messages[-1].content == "result"
    
    agent.reject_tool("call2", "tool2", "reason")
    assert agent.messages[-1].role == "tool"
    assert "rejected by human: reason" in agent.messages[-1].content

@pytest.mark.asyncio
async def test_aapprove_areject_tools(mock_provider, mock_memory):
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, memory=mock_memory)
    
    await agent.aapprove_tool("call1", "tool1", "result")
    assert agent.messages[-1].role == "tool"
    assert agent.messages[-1].content == "result"
    mock_memory.aadd_message.assert_awaited()
    
    await agent.areject_tool("call2", "tool2", "reason")
    assert agent.messages[-1].role == "tool"
    assert "rejected by human: reason" in agent.messages[-1].content

@pytest.mark.asyncio
async def test_aprepare_messages_with_plan(mock_provider, mock_workspace):
    mock_plan = MagicMock()
    mock_plan.to_markdown.return_value = "MARKDOWN_PLAN"
    mock_workspace.aget_active_plan.return_value = mock_plan
    
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, workspace=mock_workspace)
    agent.messages = [Message(role="user", content="hello")]
    
    prepared = await agent._aprepare_messages(agent.messages)
    assert "CURRENT PLAN:\nMARKDOWN_PLAN" in prepared[0].content

def test_step_sync(mock_provider, mock_event_bus):
    mock_provider.generate.return_value = Response(
        message=Message(role="assistant", content="sync response"),
        finish_reason="stop",
        usage={"prompt_tokens": 10, "completion_tokens": 5}
    )
    
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, event_bus=mock_event_bus)
    response = agent.step()
    
    assert response.message.content == "sync response"
    assert agent.usage["prompt_tokens"] == 10
    assert agent.usage["completion_tokens"] == 5
    assert mock_event_bus.publish.call_count == 3 # AgentStepStarted, TokenUsageReported, AgentStepCompleted

@pytest.mark.asyncio
async def test_astep_with_guardrails(mock_provider, mock_event_bus):
    mock_provider.agenerate.return_value = Response(
        message=Message(role="assistant", content="async response"),
        finish_reason="stop",
        usage={}
    )
    
    # Mock Guardrails
    class InputRedactGuardrail(BaseGuardrail):
        def __init__(self):
            super().__init__(GuardrailStage.INPUT, GuardrailAction.REDACT)
        async def aevaluate(self, content: str, **kwargs):
            return GuardrailResult(passed=False, action=GuardrailAction.REDACT, modified_content="redacted_input", message="")
            
    class OutputFeedbackGuardrail(BaseGuardrail):
        def __init__(self):
            super().__init__(GuardrailStage.OUTPUT, GuardrailAction.FEEDBACK)
        async def aevaluate(self, content: str, **kwargs):
            return GuardrailResult(passed=False, action=GuardrailAction.FEEDBACK, message="Be nicer")
            
    agent = Agent(
        name="A", description="B", system_prompt="Sys", provider=mock_provider,
        guardrails=[InputRedactGuardrail(), OutputFeedbackGuardrail()],
        event_bus=mock_event_bus
    )
    agent.messages = [Message(role="user", content="bad input")]
    
    response = await agent.astep()
    
    # Input should be redacted
    assert agent.messages[0].content == "redacted_input"
    # Feedback should be added as system message
    assert agent.messages[-1].role == "system"
    assert "Be nicer" in agent.messages[-1].content
    
@pytest.mark.asyncio
async def test_astep_input_block_guardrail(mock_provider, mock_event_bus):
    class BlockGuardrail(BaseGuardrail):
        def __init__(self):
            super().__init__(GuardrailStage.INPUT, GuardrailAction.BLOCK)
        async def aevaluate(self, content: str, **kwargs):
            return GuardrailResult(passed=False, action=GuardrailAction.BLOCK, message="Blocked input")
            
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, guardrails=[BlockGuardrail()], event_bus=mock_event_bus)
    agent.messages = [Message(role="user", content="block me")]
    
    with pytest.raises(Exception, match="Input blocked by guardrail"):
        await agent.astep()

@pytest.mark.asyncio
async def test_astep_output_block_guardrail(mock_provider, mock_event_bus):
    mock_provider.agenerate.return_value = Response(
        message=Message(role="assistant", content="bad response"),
        finish_reason="stop",
        usage={}
    )
    class BlockGuardrail(BaseGuardrail):
        def __init__(self):
            super().__init__(GuardrailStage.OUTPUT, GuardrailAction.BLOCK)
        async def aevaluate(self, content: str, **kwargs):
            return GuardrailResult(passed=False, action=GuardrailAction.BLOCK, message="Blocked output")
            
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, guardrails=[BlockGuardrail()], event_bus=mock_event_bus)
    agent.messages = [Message(role="user", content="hi")]
    
    with pytest.raises(Exception, match="Output blocked by guardrail"):
        await agent.astep()
        
@pytest.mark.asyncio
async def test_astep_output_redact_guardrail(mock_provider, mock_event_bus):
    mock_provider.agenerate.return_value = Response(
        message=Message(role="assistant", content="response with secret"),
        finish_reason="stop",
        usage={}
    )
    class RedactGuardrail(BaseGuardrail):
        def __init__(self):
            super().__init__(GuardrailStage.OUTPUT, GuardrailAction.REDACT)
        async def aevaluate(self, content: str, **kwargs):
            return GuardrailResult(passed=False, action=GuardrailAction.REDACT, modified_content="response with [REDACTED]", message="")
            
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, guardrails=[RedactGuardrail()], event_bus=mock_event_bus)
    agent.messages = [Message(role="user", content="hi")]
    
    response = await agent.astep()
    assert response.message.content == "response with [REDACTED]"
    assert agent.messages[-1].content == "response with [REDACTED]"

@pytest.mark.asyncio
async def test_astep_tool_injection_truncated(mock_provider, mock_event_bus):
    mock_provider.agenerate.return_value = Response(
        message=Message(role="assistant", content="response"), finish_reason="stop", usage={}
    )
    
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, event_bus=mock_event_bus)
    agent.messages = [Message(role="user", content="File content [TRUNCATED]")]
    
    await agent.astep()
    
    assert any(t.name == "read_file_chunk" for t in agent.tools)

@pytest.mark.asyncio
async def test_astep_workspace_planning_injection(mock_provider, mock_workspace, mock_event_bus):
    mock_provider.agenerate.return_value = Response(
        message=Message(role="assistant", content="response"), finish_reason="stop", usage={}
    )
    
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider, workspace=mock_workspace, event_bus=mock_event_bus)
    
    # Case 1: No active plan -> only create_plan injected
    mock_workspace.aget_active_plan.return_value = None
    await agent.astep()
    assert any(t.name == "create_plan" for t in agent.tools)
    assert not any(t.name == "update_task" for t in agent.tools)
    
    # Case 2: Active plan exists -> update_task and add_task injected too
    mock_workspace.aget_active_plan.return_value = MagicMock()
    await agent.astep()
    assert any(t.name == "update_task" for t in agent.tools)

def test_stream_sync(mock_provider):
    mock_provider.generate_stream.return_value = iter([])
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider)
    list(agent.stream())
    mock_provider.generate_stream.assert_called_once()

@pytest.mark.asyncio
async def test_astream_async(mock_provider):
    async def mock_stream():
        yield "chunk"
    mock_provider.agenerate_stream.return_value = mock_stream()
    agent = Agent(name="A", description="B", system_prompt="Sys", provider=mock_provider)
    chunks = [c async for c in agent.astream()]
    assert chunks == ["chunk"]
    mock_provider.agenerate_stream.assert_called_once()
