class OrkestraError(Exception):
    """Base exception for all Orkestra framework errors."""
    pass

class ProviderError(OrkestraError):
    """Generic error raised when an LLM provider fails."""
    pass

class AuthenticationError(ProviderError):
    """Raised when provider authentication fails (e.g., invalid API key)."""
    pass

class RateLimitError(ProviderError):
    """Raised when hitting provider rate limits."""
    pass

class ContextWindowExceededError(ProviderError):
    """Raised when the input exceeds the provider's context window."""
    pass

class ToolExecutionError(OrkestraError):
    """Raised when a tool fails to execute."""
    pass

class MaxIterationsError(OrkestraError):
    """Raised when an agent workflow exceeds the maximum allowed iterations."""
    pass

class WorkflowPausedError(OrkestraError):
    """Raised when an agent workflow is paused (e.g. for human approval)."""
    pass

class HandoffException(WorkflowPausedError):
    """Raised specifically when a handoff tool is invoked to halt the current agent."""
    def __init__(self, target_agent_name: str, context_message: str, tool_call_id: str):
        super().__init__(f"Handoff initiated to {target_agent_name}")
        self.target_agent_name = target_agent_name
        self.context_message = context_message
        self.tool_call_id = tool_call_id
