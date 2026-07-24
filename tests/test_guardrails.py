import pytest
from unittest.mock import MagicMock, AsyncMock
from orkestra.guardrails.base import GuardrailStage, GuardrailAction
from orkestra.guardrails.regex import RegexGuardrail
from orkestra.guardrails.llm_judge import LLMJudgeGuardrail
from orkestra.core.messages import Message

@pytest.mark.asyncio
async def test_regex_guardrail_block():
    guardrail = RegexGuardrail(
        stage=GuardrailStage.INPUT,
        action_on_fail=GuardrailAction.BLOCK,
        pattern=r"SECRET_\w+",
        error_message="Found a secret token!"
    )
    
    # Should pass
    res1 = await guardrail.aevaluate("Hello world")
    assert res1.passed is True
    
    # Should fail and block
    res2 = await guardrail.aevaluate("Here is my SECRET_123 token")
    assert res2.passed is False
    assert res2.action == GuardrailAction.BLOCK
    assert res2.message == "Found a secret token!"

@pytest.mark.asyncio
async def test_regex_guardrail_redact():
    guardrail = RegexGuardrail(
        stage=GuardrailStage.OUTPUT,
        action_on_fail=GuardrailAction.REDACT,
        pattern=r"\d{3}-\d{2}-\d{4}",
        error_message="SSN detected and redacted",
        replacement="[REDACTED SSN]"
    )
    
    res = await guardrail.aevaluate("My SSN is 123-45-6789.")
    assert res.passed is False
    assert res.action == GuardrailAction.REDACT
    assert res.modified_content == "My SSN is [REDACTED SSN]."

@pytest.mark.asyncio
async def test_llm_judge_guardrail():
    mock_provider = AsyncMock()
    # Mock a PASS
    mock_provider.agenerate.return_value = MagicMock(message=Message(role="assistant", content="PASS"))
    
    guardrail = LLMJudgeGuardrail(
        stage=GuardrailStage.ACTION,
        action_on_fail=GuardrailAction.FEEDBACK,
        prompt="Check if this is safe.",
        provider=mock_provider
    )
    
    res1 = await guardrail.aevaluate("print('hello')")
    assert res1.passed is True
    
    # Mock a FAIL
    mock_provider.agenerate.return_value = MagicMock(message=Message(role="assistant", content="FAIL: Contains rm -rf"))
    res2 = await guardrail.aevaluate("rm -rf /")
    assert res2.passed is False
    assert res2.action == GuardrailAction.FEEDBACK
    assert res2.message == "Contains rm -rf"
