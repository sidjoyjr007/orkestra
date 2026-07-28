import pytest
from unittest.mock import MagicMock
from orkestra.core.executor import ToolExecutor
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, ToolCall
from orkestra.core.tools import HostTool
from orkestra.guardrails.base import BaseGuardrail, GuardrailStage, GuardrailAction, GuardrailResult
from orkestra.core.exceptions import WorkflowPausedError

@pytest.mark.asyncio
async def test_executor_guardrail_block():
    mock_provider = MagicMock()
    
    class MockBlockGuardrail(BaseGuardrail):
        stage = GuardrailStage.ACTION
        async def aevaluate(self, content, context=None, agent=None):
            return GuardrailResult(passed=False, action=GuardrailAction.BLOCK, message="Blocked by guardrail")

    def mock_tool(**kwargs): return "success"
    tool = HostTool(name="test_tool", description="Test", schema={}, func=mock_tool)
    
    agent = Agent(
        name="test", 
        description="Test", 
        system_prompt="Sys", 
        provider=mock_provider, 
        tools=[tool], 
        guardrails=[MockBlockGuardrail(stage=GuardrailStage.ACTION, action_on_fail=GuardrailAction.BLOCK)]
    )
    executor = ToolExecutor(agent)
    
    await executor.aexecute([ToolCall(id="t1", function_name="test_tool", function_arguments='{}')])
    
    msgs = agent.messages
    tool_msg = next((m for m in msgs if m.role == "tool"), None)
    assert tool_msg is not None
    assert "Blocked by guardrail" in tool_msg.content

@pytest.mark.asyncio
async def test_executor_guardrail_redact():
    mock_provider = MagicMock()
    
    class MockRedactGuardrail(BaseGuardrail):
        stage = GuardrailStage.ACTION
        async def aevaluate(self, content, context=None, agent=None):
            # Redacts input args to something else
            return GuardrailResult(passed=False, action=GuardrailAction.REDACT, modified_content='{"arg": "redacted"}')

    def mock_tool(arg=None, **kwargs): return f"success {arg}"
    tool = HostTool(name="test_tool", description="Test", schema={}, func=mock_tool)
    
    agent = Agent(
        name="test", 
        description="Test", 
        system_prompt="Sys", 
        provider=mock_provider, 
        tools=[tool], 
        guardrails=[MockRedactGuardrail(stage=GuardrailStage.ACTION, action_on_fail=GuardrailAction.REDACT)]
    )
    executor = ToolExecutor(agent)
    
    await executor.aexecute([ToolCall(id="t1", function_name="test_tool", function_arguments='{"arg": "secret"}')])
    
    msgs = agent.messages
    tool_msg = next((m for m in msgs if m.role == "tool"), None)
    assert tool_msg is not None
    assert "success redacted" in tool_msg.content

def test_executor_anti_loop():
    mock_provider = MagicMock()
    
    def mock_tool(**kwargs): return "success"
    tool = HostTool(name="test_tool", description="Test", schema={}, func=mock_tool)
    
    agent = Agent(name="test", description="Test", system_prompt="Sys", provider=mock_provider, tools=[tool])
    
    # Pre-populate history with 3 identical tool calls to trigger loop prevention
    for _ in range(3):
        agent.add_message(Message(
            role="assistant", 
            content="Use tool", 
            tool_calls=[ToolCall(id="t1", function_name="test_tool", function_arguments='{}')]
        ))
        
    executor = ToolExecutor(agent)
    executor.execute([ToolCall(id="t1", function_name="test_tool", function_arguments='{}')])
    
    msgs = agent.messages
    tool_msg = msgs[-1]
    assert "SYSTEM WARNING: You have executed the tool" in tool_msg.content
