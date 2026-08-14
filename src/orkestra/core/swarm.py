import asyncio
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field
from orkestra.core.tools import Tool, HostTool
from orkestra.core.messages import Message

class HandoffException(Exception):
    """
    Exception raised when an agent decides to hand off the conversation 
    to another agent. Intercepted by the Executor.
    """
    def __init__(self, target_agent_id: str, reason: str, context: Optional[Dict[str, Any]] = None):
        self.target_agent_id = target_agent_id
        self.reason = reason
        self.context = context or {}
        super().__init__(f"Handoff to {target_agent_id} due to: {reason}")

def _handoff_func(target_agent_id: str, reason: str, context: str = "{}") -> str:
    """
    Hands off the conversation to another agent.
    """
    import json
    parsed_context = {}
    if context:
        try:
            parsed_context = json.loads(context)
        except Exception:
            pass
            
    raise HandoffException(target_agent_id=target_agent_id, reason=reason, context=parsed_context)

def get_handoff_tool(available_agent_ids: List[str]) -> Tool:
    schema = {
        "type": "object",
        "properties": {
            "target_agent_id": {
                "type": "string",
                "enum": available_agent_ids,
                "description": "The ID of the agent to hand off to."
            },
            "reason": {
                "type": "string",
                "description": "Explanation of why you are handing off."
            },
            "context": {
                "type": "string",
                "description": "JSON string containing any critical context the new agent needs."
            }
        },
        "required": ["target_agent_id", "reason"]
    }
    full_schema = {
        "type": "function",
        "function": {
            "name": "handoff_to_agent",
            "description": "Hand off the current user conversation to a different specialized agent.",
            "parameters": schema
        }
    }
    
    return HostTool(
        name="handoff_to_agent",
        description="Hand off the current user conversation to a different specialized agent.",
        func=_handoff_func,
        schema=full_schema
    )

def _delegate_func(target_agent_id: str, task: str) -> str:
    """
    In a real implementation, this would dynamically look up the target agent
    and spawn a nested Executor to resolve the task, returning the final output.
    Since Tools are synchronous by default in the basic schema, we can return a directive 
    or use an AsyncTool variant.
    """
    # For now, we mock the delegation response or rely on the Executor handling it.
    # A true Swarm implementation will intercept this in the Executor.
    return f"Delegation to {target_agent_id} requested for task: {task}. (Nested execution not fully linked in mock)."

def get_delegate_tool(available_agent_ids: List[str]) -> Tool:
    schema = {
        "type": "object",
        "properties": {
            "target_agent_id": {
                "type": "string",
                "enum": available_agent_ids,
                "description": "The ID of the agent to delegate the task to."
            },
            "task": {
                "type": "string",
                "description": "Detailed description of the task for the sub-agent."
            }
        },
        "required": ["target_agent_id", "task"]
    }
    
    full_schema = {
        "type": "function",
        "function": {
            "name": "delegate_task",
            "description": "Delegate a sub-task to another agent, wait for their response, and use it to continue your work.",
            "parameters": schema
        }
    }
    
    return HostTool(
        name="delegate_task",
        description="Delegate a sub-task to another agent, wait for their response, and use it to continue your work.",
        func=_delegate_func,
        schema=full_schema
    )
