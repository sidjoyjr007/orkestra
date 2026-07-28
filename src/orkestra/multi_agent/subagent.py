import uuid
import copy
from typing import List, Optional
from orkestra.core.tools import Tool
from orkestra.events.bus import EventBus
from orkestra.events.base import SubAgentStarted, SubAgentCompleted
from orkestra.core.messages import Message
from orkestra.workflows.runner import AgentRunner
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.core.telemetry import get_logger
from orkestra.core.exceptions import WorkflowPausedError

logger = get_logger("orkestra.multi_agent.subagent")

class DynamicSubAgentTool(Tool):
    """
    A dynamic tool that allows a Manager Agent to spawn a worker sub-agent, 
    delegate a specific task to it, and wait for the result.
    """
    def __init__(self, available_agents: List[str], registry: AgentRegistry, event_bus: EventBus, manager_agent_name: str, parent_session_id: str):
        schema = {
            "type": "function",
            "function": {
                "name": "delegate_to_subagent",
                "description": "Spawn a specialized sub-agent to handle a specific task for you. You will pause while they work, and their final result will be returned to you.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "target_agent": {
                            "type": "string",
                            "enum": available_agents,
                            "description": "The specific name of the agent you want to delegate to."
                        },
                        "task_description": {
                            "type": "string",
                            "description": "A highly detailed prompt explaining exactly what you want the sub-agent to do."
                        }
                    },
                    "required": ["target_agent", "task_description"]
                }
            }
        }
        super().__init__(
            name="delegate_to_subagent",
            description="Spawn a specialized sub-agent to handle a specific task.",
            func=self.run,
            schema=schema
        )
        self.available_agents = available_agents
        self.registry = registry
        self.event_bus = event_bus
        self.manager_agent_name = manager_agent_name
        self.parent_session_id = parent_session_id

    async def _execute_subagent(self, target_agent: str, task_description: str) -> str:
        if target_agent not in self.available_agents:
            return f"Error: Agent '{target_agent}' is not registered."

        # Pull the template from the registry
        template_agent = self.registry.get_agent(target_agent)
        if not template_agent:
            return f"Error: Could not retrieve '{target_agent}' from registry."

        # Create memory isolation by giving the worker a unique sub-session
        sub_session_id = f"{self.parent_session_id}_sub_{target_agent}_{uuid.uuid4().hex[:8]}"
        
        logger.info(f"Manager '{self.manager_agent_name}' spawning sub-agent '{target_agent}' (Session: {sub_session_id})")

        # The registry.get_agent() method now returns a fresh clone of the template agent!
        worker_agent = template_agent
        worker_agent.session_id = sub_session_id
        
        # We must also clear its messages so it doesn't accidentally load previous state if memory was reused in process
        # Wait, the memory backend pulls by session_id, so it will be blank!
        
        # Fire Started event
        await self.event_bus.apublish(
            SubAgentStarted(
                manager_agent_name=self.manager_agent_name,
                sub_agent_name=target_agent,
                sub_session_id=sub_session_id,
                task_description=task_description
            )
        )

        # Inject the task as the first user message
        task_msg = Message(role="user", content=f"MANAGER DELEGATION: {task_description}")
        await worker_agent.aadd_message(task_msg)

        # Run the sub-agent via AgentRunner
        runner = AgentRunner(agent=worker_agent, event_bus=self.event_bus)
        
        try:
            await runner.arun()
        except WorkflowPausedError:
            # Re-raise so the orchestrator halts appropriately
            raise
        except Exception as e:
            logger.error(f"Sub-agent {target_agent} failed: {e}")
            return f"Error: Sub-agent crashed with exception: {str(e)}"

        # The sub-agent has finished its run. Grab its last message!
        # If we successfully ran, the last message in `worker_agent.messages` is the final answer.
        if worker_agent.messages:
            last_msg = worker_agent.messages[-1]
            if last_msg.role == "assistant" and last_msg.content:
                result = last_msg.content
            else:
                # Iterate backwards to find the last assistant message with content
                result = "Error: Sub-agent did not return a valid text response."
                for msg in reversed(worker_agent.messages):
                    if msg.role == "assistant" and msg.content:
                        result = msg.content
                        break
        else:
            result = "Error: Sub-agent returned no messages."

        # Fire Completed event
        await self.event_bus.apublish(
            SubAgentCompleted(
                manager_agent_name=self.manager_agent_name,
                sub_agent_name=target_agent,
                sub_session_id=sub_session_id,
                result=result
            )
        )

        logger.info(f"Sub-agent '{target_agent}' finished. Returning result to '{self.manager_agent_name}'.")
        return result

    def run(self, target_agent: str, task_description: str, **kwargs) -> str:
        # We can't easily run async code from sync run without an event loop trick, 
        # but Orkestra prefers async execution natively anyway.
        return "Error: delegate_to_subagent must be called asynchronously."

    async def arun(self, target_agent: str, task_description: str, **kwargs) -> str:
        return await self._execute_subagent(target_agent, task_description)

class DynamicParallelSubAgentTool(Tool):
    """
    A dynamic tool that allows a Manager Agent to spawn multiple worker sub-agents 
    in parallel, delegating tasks to them and waiting for all results simultaneously.
    """
    def __init__(self, available_agents: List[str], registry: AgentRegistry, event_bus: EventBus, manager_agent_name: str, parent_session_id: str):
        schema = {
            "type": "function",
            "function": {
                "name": "delegate_parallel_subagents",
                "description": "Spawn multiple specialized sub-agents to handle specific tasks for you in parallel. You will pause while they work, and their final results will be returned to you in a single report.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "delegations": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "target_agent": {
                                        "type": "string",
                                        "enum": available_agents,
                                        "description": "The specific name of the agent you want to delegate to."
                                    },
                                    "task_description": {
                                        "type": "string",
                                        "description": "A highly detailed prompt explaining exactly what you want the sub-agent to do."
                                    }
                                },
                                "required": ["target_agent", "task_description"]
                            },
                            "description": "A list of delegations to execute in parallel."
                        }
                    },
                    "required": ["delegations"]
                }
            }
        }
        super().__init__(
            name="delegate_parallel_subagents",
            description="Spawn multiple specialized sub-agents to handle specific tasks in parallel.",
            func=self.run,
            schema=schema
        )
        self.available_agents = available_agents
        self.registry = registry
        self.event_bus = event_bus
        self.manager_agent_name = manager_agent_name
        self.parent_session_id = parent_session_id
        
        # We reuse the logic from DynamicSubAgentTool by instantiating one internally
        self._single_tool = DynamicSubAgentTool(
            available_agents=available_agents,
            registry=registry,
            event_bus=event_bus,
            manager_agent_name=manager_agent_name,
            parent_session_id=parent_session_id
        )

    def run(self, delegations: List[dict], **kwargs) -> str:
        return "Error: delegate_parallel_subagents must be called asynchronously."

    async def arun(self, delegations: List[dict], **kwargs) -> str:
        if not delegations:
            return "Error: No delegations provided."
            
        logger.info(f"Manager '{self.manager_agent_name}' spawning {len(delegations)} parallel sub-agents")
        
        import asyncio
        tasks = []
        for i, delegation in enumerate(delegations):
            target = delegation.get("target_agent")
            task_desc = delegation.get("task_description")
            if not target or not task_desc:
                continue
                
            # Create a wrapped coroutine to identify which delegation it belongs to
            async def run_delegation(t=target, desc=task_desc, idx=i):
                result = await self._single_tool.arun(target_agent=t, task_description=desc)
                return f"--- Result from {t} (Task {idx+1}) ---\n{result}\n"
                
            tasks.append(run_delegation())
            
        if not tasks:
            return "Error: Invalid delegations format."
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        final_report = f"Parallel Execution Report for {len(delegations)} tasks:\n\n"
        for i, res in enumerate(results):
            if isinstance(res, Exception):
                final_report += f"--- Result from Task {i+1} ---\nError during execution: {str(res)}\n\n"
            else:
                final_report += res + "\n"
                
        return final_report
