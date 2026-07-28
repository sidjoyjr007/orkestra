from typing import Dict, Any, Optional
from orkestra.core.tools import Tool
from orkestra.events.bus import EventBus
from orkestra.events.base import HandoffRequested, WorkflowPaused
from orkestra.core.exceptions import WorkflowPausedError, HandoffException
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.multi_agent.handoff")

class HandoffTool(Tool):
    """
    A specialized tool that allows an agent to hand off the current session to another agent.
    When invoked, it fires a HandoffRequested event and immediately pauses the current workflow.
    """
    def __init__(self, target_agent_name: str, event_bus: EventBus, source_agent_name: str, description: Optional[str] = None):
        schema = {
            "type": "function",
            "function": {
                "name": f"handoff_to_{target_agent_name}",
                "description": description or f"Hand off the conversation to {target_agent_name}. Provide a context_message explaining what needs to be done and what you have accomplished so far.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "context_message": {
                            "type": "string",
                            "description": "Detailed instructions and context for the receiving agent."
                        }
                    },
                    "required": ["context_message"]
                }
            }
        }
        super().__init__(
            name=f"handoff_to_{target_agent_name}",
            description=description or f"Hand off the conversation to {target_agent_name}. Provide a context_message explaining what needs to be done and what you have accomplished so far.",
            func=self.run,
            schema=schema
        )
        self.target_agent_name = target_agent_name
        self.event_bus = event_bus
        self.source_agent_name = source_agent_name
        self._is_handoff_tool = True # Internal marker

    def run(self, context_message: str, **kwargs) -> str:
        """
        Synchronous run. Emits the handoff event and halts the current executor.
        """
        logger.info(f"Agent '{self.source_agent_name}' initiating handoff to '{self.target_agent_name}'")
        
        # In a real tool execution context, we need the tool_call_id.
        # We'll expect the Orchestrator/Executor to handle the pausing. 
        # But this tool will just raise a WorkflowPausedError natively.
        
        # We can't access tool_call_id easily inside the tool unless passed in kwargs by Executor.
        # So the Executor should intercept tools with `_is_handoff_tool = True`
        # and handle them specially, or pass tool_call_id. 
        
        # Let's use a special return string that the Executor intercepts, OR raise a specific Exception.
        # Actually, let's just return a standard string, and the Orchestrator will have caught the event anyway!
        
        tool_call_id = kwargs.get("__tool_call_id", "unknown")
        
        self.event_bus.publish(
            HandoffRequested(
                source_agent_name=self.source_agent_name,
                target_agent_name=self.target_agent_name,
                context_message=context_message,
                tool_call_id=tool_call_id
            )
        )
        
        # Tell the current executor to halt
        self.event_bus.publish(WorkflowPaused(agent_name=self.source_agent_name))
        
        raise HandoffException(
            target_agent_name=self.target_agent_name,
            context_message=context_message,
            tool_call_id=tool_call_id
        )

    async def arun(self, context_message: str, **kwargs) -> str:
        """
        Asynchronous run. Emits the handoff event and halts the current executor.
        """
        logger.info(f"Agent '{self.source_agent_name}' initiating handoff to '{self.target_agent_name}'")
        tool_call_id = kwargs.get("__tool_call_id", "unknown")
        
        await self.event_bus.apublish(
            HandoffRequested(
                source_agent_name=self.source_agent_name,
                target_agent_name=self.target_agent_name,
                context_message=context_message,
                tool_call_id=tool_call_id
            )
        )
        
        await self.event_bus.apublish(WorkflowPaused(agent_name=self.source_agent_name))
        
        raise HandoffException(
            target_agent_name=self.target_agent_name,
            context_message=context_message,
            tool_call_id=tool_call_id
        )

class DynamicHandoffTool(Tool):
    """
    A dynamic handoff tool that allows an agent to route the conversation to any 
    other agent registered in the multi-agent system. The Orchestrator automatically 
    populates the available targets based on the registry.
    """
    def __init__(self, available_agents: list[str], event_bus: EventBus, source_agent_name: str):
        schema = {
            "type": "function",
            "function": {
                "name": "handoff_to_agent",
                "description": "Hand off the conversation to another specialized agent. Use this when the user's request falls outside your domain of expertise, or you have finished your part of the task.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_agent": {
                            "type": "string",
                            "enum": available_agents,
                            "description": "The exact name of the agent to hand off to."
                        },
                        "context_message": {
                            "type": "string",
                            "description": "Detailed instructions and context for the receiving agent explaining what needs to be done next."
                        }
                    },
                    "required": ["target_agent", "context_message"]
                }
            }
        }
        super().__init__(
            name="handoff_to_agent",
            description="Hand off the conversation to another specialized agent.",
            func=self.run,
            schema=schema
        )
        self.available_agents = available_agents
        self.event_bus = event_bus
        self.source_agent_name = source_agent_name

    def run(self, target_agent: str, context_message: str, **kwargs) -> str:
        if target_agent not in self.available_agents:
            return f"Error: Agent '{target_agent}' is not available."
            
        logger.info(f"Agent '{self.source_agent_name}' dynamically handing off to '{target_agent}'")
        tool_call_id = kwargs.get("__tool_call_id", "unknown")
        
        self.event_bus.publish(
            HandoffRequested(
                source_agent_name=self.source_agent_name,
                target_agent_name=target_agent,
                context_message=context_message,
                tool_call_id=tool_call_id
            )
        )
        self.event_bus.publish(WorkflowPaused(agent_name=self.source_agent_name))
        
        raise HandoffException(
            target_agent_name=target_agent,
            context_message=context_message,
            tool_call_id=tool_call_id
        )

    async def arun(self, target_agent: str, context_message: str, **kwargs) -> str:
        if target_agent not in self.available_agents:
            return f"Error: Agent '{target_agent}' is not available."
            
        logger.info(f"Agent '{self.source_agent_name}' dynamically handing off to '{target_agent}'")
        tool_call_id = kwargs.get("__tool_call_id", "unknown")
        
        await self.event_bus.apublish(
            HandoffRequested(
                source_agent_name=self.source_agent_name,
                target_agent_name=target_agent,
                context_message=context_message,
                tool_call_id=tool_call_id
            )
        )
        await self.event_bus.apublish(WorkflowPaused(agent_name=self.source_agent_name))
        
        raise HandoffException(
            target_agent_name=target_agent,
            context_message=context_message,
            tool_call_id=tool_call_id
        )
