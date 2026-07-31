from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

@dataclass
class Event:
    """Base class for all Orkestra events."""
    timestamp: datetime = field(init=False)

    def __post_init__(self):
        self.timestamp = datetime.utcnow()

@dataclass
class AgentStepStarted(Event):
    """Emitted when an agent begins a single turn/step."""
    agent_name: str
    session_id: str

@dataclass
class AgentStepCompleted(Event):
    """Emitted when an agent completes a single turn/step."""
    agent_name: str
    session_id: str
    response_content: Optional[str]
    tool_calls: int

@dataclass
class TokenUsageReported(Event):
    """Emitted when an LLM provider reports token usage."""
    agent_name: str
    session_id: str
    prompt_tokens: int
    completion_tokens: int

@dataclass
class ToolExecutionStarted(Event):
    """Emitted when a tool begins execution."""
    agent_name: str
    tool_name: str
    tool_args: Dict[str, Any]

@dataclass
class ToolExecutionCompleted(Event):
    """Emitted when a tool completes execution."""
    agent_name: str
    tool_name: str
    result: str
    error: Optional[str] = None

@dataclass
class WorkflowStarted(Event):
    """Emitted when a runner begins an agent workflow."""
    agent_name: str
    session_id: str
    max_iterations: int

@dataclass
class WorkflowCompleted(Event):
    """Emitted when a runner finishes an agent workflow."""
    agent_name: str
    session_id: str
    total_iterations: int

@dataclass
class ProviderRetrying(Event):
    """Emitted when an LLM provider encounters an error and is retrying."""
    provider_name: str
    attempt_number: int
    wait_time_seconds: float
    error: str

@dataclass
class HumanApprovalRequested(Event):
    """Emitted when a tool requires human approval before execution."""
    agent_name: str
    tool_name: str
    tool_call_id: str
    tool_args: Dict[str, Any]
    approval_type: str = "yes/no"

@dataclass
class HumanApprovalProvided(Event):
    """Emitted when a human provides an approval decision for a pending tool."""
    tool_call_id: str
    result: str

@dataclass
class WorkflowPaused(Event):
    """Emitted when a workflow pauses execution (e.g. waiting for HITL)."""
    agent_name: str
    
@dataclass
class HandoffRequested(Event):
    """Fired when an agent uses the handoff tool to pass control to another agent."""
    source_agent_name: str
    target_agent_name: str
    context_message: str
    tool_call_id: str

@dataclass
class SubAgentStarted(Event):
    """Fired when a manager agent spawns a sub-agent."""
    manager_agent_name: str
    sub_agent_name: str
    sub_session_id: str
    task_description: str

@dataclass
class SubAgentCompleted(Event):
    """Fired when a sub-agent completes its task and returns the result to the manager."""
    manager_agent_name: str
    sub_agent_name: str
    sub_session_id: str
    result: str

@dataclass
class TaskCompletedEvent(Event):
    """Fired when an asynchronous background task completes, used to wake up sleeping agents."""
    agent_name: str
    session_id: str
    tool_call_id: str
    result: str

@dataclass
class GuardrailTriggered(Event):
    """Fired when a guardrail blocks, redacts, or feeds back content."""
    agent_name: str
    session_id: str
    stage: str
    action_taken: str
    message: str
    modified_content: Optional[str] = None

@dataclass
class MemoryReadEvent(Event):
    """Fired when conversation history is fetched from memory."""
    session_id: str
    message_count: int

@dataclass
class MemoryWrittenEvent(Event):
    """Fired when a message is saved to memory."""
    session_id: str
    role: str
    
@dataclass
class WorkspaceReadEvent(Event):
    """Fired when workspace plans/tasks are retrieved."""
    session_id: str
    items_retrieved: int
    
@dataclass
class WorkspaceWrittenEvent(Event):
    """Fired when workspace plans/tasks are updated or created."""
    session_id: str
    action: str
    
@dataclass
class ToolSearchStarted(Event):
    """Fired when ToolRegistry begins searching ChromaDB for relevant tools."""
    agent_id: str
    query: str

@dataclass
class ToolSearchCompleted(Event):
    """Fired when ToolRegistry completes a search."""
    agent_id: str
    tools_found: int

@dataclass
class ContextCompactionStarted(Event):
    """Fired when token summarization begins."""
    session_id: str
    current_tokens: int
    max_tokens: int

@dataclass
class ContextCompactionCompleted(Event):
    """Fired when token summarization completes."""
    session_id: str
    new_tokens: int
