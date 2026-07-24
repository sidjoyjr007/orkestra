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
