import abc
from enum import Enum
from typing import Optional, Dict, Any

class GuardrailStage(Enum):
    INPUT = "INPUT"
    ACTION = "ACTION"
    OUTPUT = "OUTPUT"
    
class GuardrailAction(Enum):
    BLOCK = "BLOCK"
    FEEDBACK = "FEEDBACK"
    REDACT = "REDACT"
    
class GuardrailResult:
    def __init__(self, passed: bool, action: Optional[GuardrailAction] = None, message: str = "", modified_content: str = ""):
        self.passed = passed
        self.action = action
        self.message = message
        self.modified_content = modified_content

class BaseGuardrail(abc.ABC):
    def __init__(self, stage: GuardrailStage, action_on_fail: GuardrailAction):
        self.stage = stage
        self.action_on_fail = action_on_fail
        
    @abc.abstractmethod
    async def aevaluate(self, content: str, context: Optional[Dict[str, Any]] = None, agent: Any = None) -> GuardrailResult:
        """
        Evaluate the content against the guardrail logic.
        content: The text to evaluate (e.g. user prompt, tool arguments, or agent response)
        context: Optional extra contextual info (like tool_name for ACTION stage)
        agent: The Agent instance running the workflow, allowing access to its provider.
        """
        pass
