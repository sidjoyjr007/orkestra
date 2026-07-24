from typing import Optional, Dict, Any
from orkestra.guardrails.base import BaseGuardrail, GuardrailStage, GuardrailAction, GuardrailResult
from orkestra.core.messages import Message

class LLMJudgeGuardrail(BaseGuardrail):
    def __init__(self, stage: GuardrailStage, action_on_fail: GuardrailAction, prompt: str, provider=None):
        super().__init__(stage, action_on_fail)
        self.prompt = prompt
        self.provider = provider
        
    async def aevaluate(self, content: str, context: Optional[Dict[str, Any]] = None, agent: Any = None) -> GuardrailResult:
        if not content:
            return GuardrailResult(passed=True)
            
        provider_to_use = self.provider or (agent.provider if agent else None)
        if not provider_to_use:
            raise ValueError("No provider available for LLMJudgeGuardrail.")
            
        # Build evaluation prompt
        eval_prompt = f"{self.prompt}\n\nCONTENT TO EVALUATE:\n{content}\n\nReturn EXACTLY 'PASS' if the content passes the rules, or 'FAIL: <reason>' if it fails."
        
        if self.action_on_fail == GuardrailAction.REDACT:
            eval_prompt += "\nIf you must REDACT it, return 'REDACT: <the modified content>'."
            
        messages = [Message(role="user", content=eval_prompt)]
        
        response = await provider_to_use.agenerate(messages)
        result_text = response.message.content.strip()
        
        if result_text.startswith("PASS"):
            return GuardrailResult(passed=True)
        elif result_text.startswith("REDACT:") and self.action_on_fail == GuardrailAction.REDACT:
            modified = result_text.replace("REDACT:", "", 1).strip()
            return GuardrailResult(passed=False, action=self.action_on_fail, message="Content was redacted by LLM Judge.", modified_content=modified)
        else:
            reason = result_text.replace("FAIL:", "", 1).strip() if result_text.startswith("FAIL:") else result_text
            return GuardrailResult(passed=False, action=self.action_on_fail, message=reason)
