import json
from typing import List, Dict
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, ToolCall, Response
from orkestra.core.exceptions import MaxIterationsError, WorkflowPausedError
from orkestra.events.bus import EventBus
import asyncio
from orkestra.events.base import WorkflowStarted, WorkflowCompleted, ToolExecutionStarted, ToolExecutionCompleted, HumanApprovalRequested, HumanApprovalProvided, WorkflowPaused
from orkestra.core.prompts import TOOL_LOOP_WARNING
from orkestra.guardrails.base import GuardrailStage, GuardrailAction
from orkestra.core.prompts import TOOL_LOOP_WARNING

from orkestra.core.executor import ToolExecutor
from orkestra.core.state import AgentStateSerializer
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.workflows.runner")

class AgentRunner:
    """
    Executes an agent's run loop, automatically handling tool calls and Human-in-the-Loop pauses.
    """
    def __init__(self, agent: Agent, event_bus: EventBus = None):
        self.agent = agent
        self.event_bus = event_bus
        self.executor = ToolExecutor(agent=self.agent, event_bus=self.event_bus)

    def _get_unanswered_tools(self) -> List[ToolCall]:
        if not self.agent.messages:
            return []
        
        # Find the last assistant message
        last_assistant_msg = None
        for msg in reversed(self.agent.messages):
            if msg.role == "assistant":
                last_assistant_msg = msg
                break
                
        if not last_assistant_msg or not last_assistant_msg.tool_calls:
            return []
            
        answered_ids = {m.tool_call_id for m in self.agent.messages if m.role == "tool" and m.tool_call_id}
        return [tc for tc in last_assistant_msg.tool_calls if tc.id not in answered_ids]

    def run(self, **kwargs):
        """Run the agent loop synchronously."""
        logger.info(f"Starting synchronous run for agent '{self.agent.name}' (ID: {self.agent.id})")
        if self.event_bus:
            self.event_bus.publish(WorkflowStarted(agent_name=self.agent.name, session_id=self.agent.session_id, max_iterations=self.agent.max_iterations))
            
        for i in range(self.agent.max_iterations):
            logger.debug(f"Agent '{self.agent.name}' iteration {i+1}/{self.agent.max_iterations}")
            unanswered = self._get_unanswered_tools()
            if unanswered:
                self.executor.execute(unanswered)
                continue
                
            response = self.agent.step(**kwargs)
            
            if not response.message.tool_calls:
                if self.event_bus:
                    self.event_bus.publish(WorkflowCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, total_iterations=i+1))
                import asyncio
                if self.agent.memory:
                    # Sync fallback
                    asyncio.run(self.agent.memory.asave_checkpoint(self.agent.session_id, AgentStateSerializer.to_dict(self.agent)))
                return response
                
            self.executor.execute(response.message.tool_calls)
            
            if self.agent.memory:
                import asyncio
                asyncio.run(self.agent.memory.asave_checkpoint(self.agent.session_id, AgentStateSerializer.to_dict(self.agent)))
                
        raise MaxIterationsError(f"Agent '{self.agent.name}' reached the maximum of {self.agent.max_iterations} iterations without providing a final response.")

    async def arun(self, **kwargs):
        """Run the agent loop asynchronously."""
        logger.info(f"Starting asynchronous run for agent '{self.agent.name}' (ID: {self.agent.id})")
        if self.event_bus:
            await self.event_bus.apublish(WorkflowStarted(agent_name=self.agent.name, session_id=self.agent.session_id, max_iterations=self.agent.max_iterations))
            
        for i in range(self.agent.max_iterations):
            logger.debug(f"Agent '{self.agent.name}' iteration {i+1}/{self.agent.max_iterations}")
            unanswered = self._get_unanswered_tools()
            if unanswered:
                await self.executor.aexecute(unanswered)
                continue
                
            # Semantic Tool Routing (Tool RAG) Pre-Step
            if hasattr(self.agent, 'tool_registry') and self.agent.tool_registry:
                self.agent.tool_registry.inject_semantic_tools(self.agent)
                
            response = await self.agent.astep(**kwargs)
            
            if not response.message.tool_calls:
                if self.event_bus:
                    await self.event_bus.apublish(WorkflowCompleted(agent_name=self.agent.name, session_id=self.agent.session_id, total_iterations=i+1))
                if self.agent.memory:
                    await self.agent.memory.asave_checkpoint(self.agent.session_id, AgentStateSerializer.to_dict(self.agent))
                return response
                
            await self.executor.aexecute(response.message.tool_calls)
            
            if self.agent.memory:
                await self.agent.memory.asave_checkpoint(self.agent.session_id, AgentStateSerializer.to_dict(self.agent))
                
        raise MaxIterationsError(f"Agent '{self.agent.name}' reached the maximum of {self.agent.max_iterations} iterations without providing a final response.")

