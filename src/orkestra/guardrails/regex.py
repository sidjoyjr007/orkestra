import re
from typing import Optional, Dict, Any
from orkestra.guardrails.base import BaseGuardrail, GuardrailStage, GuardrailAction, GuardrailResult

class RegexGuardrail(BaseGuardrail):
    def __init__(self, stage: GuardrailStage, action_on_fail: GuardrailAction, pattern: str, error_message: str, replacement: str = "***"):
        super().__init__(stage, action_on_fail)
        self.pattern = re.compile(pattern)
        self.error_message = error_message
        self.replacement = replacement
        
    async def aevaluate(self, content: str, context: Optional[Dict[str, Any]] = None, agent: Any = None) -> GuardrailResult:
        if not content:
            return GuardrailResult(passed=True)
            
        if self.pattern.search(content):
            if self.action_on_fail == GuardrailAction.REDACT:
                modified = self.pattern.sub(self.replacement, content)
                return GuardrailResult(passed=False, action=self.action_on_fail, message=self.error_message, modified_content=modified)
            else:
                return GuardrailResult(passed=False, action=self.action_on_fail, message=self.error_message)
                
        return GuardrailResult(passed=True)
