import asyncio
from typing import Dict, List, Any, Optional, Callable, Awaitable
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.core.tools import HostTool
from orkestra.core.messages import Message
from orkestra.core.swarm import HandoffException, get_handoff_tool
from orkestra.events.bus import EventBus

class SwarmExecutor:
    """
    Executes a Swarm consisting of a Leader Agent and multiple Subagents.
    Provides native delegation and handoff tools to the Leader.
    """
    def __init__(
        self, 
        leader: Agent, 
        subagent_factory: Callable[[str], Awaitable[Optional[Agent]]],
        event_bus: Optional[EventBus] = None
    ):
        """
        :param leader: The primary entrypoint agent.
        :param subagent_factory: An async callback that takes an agent_id and returns an isolated Agent instance.
        :param event_bus: An optional EventBus for streaming telemetry.
        """
        self.leader = leader
        self.subagent_factory = subagent_factory
        self.event_bus = event_bus
        self.current_agent = self.leader
        
    def _inject_swarm_tools(self, agent: Agent, subagents_info: List[Dict[str, Any]]):
        available_agent_ids = [sa["agent_id"] for sa in subagents_info]
        
        # Inject Subagents Context into System Prompt
        context_str = "\n".join([f"- ID: {sa['agent_id']}\n  Name: {sa['name']}\n  Role: {sa['role_description']}" for sa in subagents_info])
        injection_marker = "### SWARM SUBAGENTS ###"
        if injection_marker not in agent.system_prompt:
            agent.system_prompt += f"\n\n{injection_marker}\nYou are the Leader of a Swarm. You can delegate tasks to the following subagents using your delegate tools:\n{context_str}\n"

        # Handoff Tool
        handoff_tool = get_handoff_tool(available_agent_ids)
        
        # Delegate Tool
        async def _delegate_func(target_agent_id: str, task: str) -> str:
            subagent = await self.subagent_factory(target_agent_id)
            if not subagent:
                return f"Error: Subagent {target_agent_id} not found or not authorized for this Swarm."
                
            # Deterministic isolated planning session for the subagent
            subagent.session_id = f"{agent.session_id}_{target_agent_id}"
                
            # Run the subagent on the isolated task
            subagent.add_message(Message(role="user", content=task))
            sub_executor = AgentRunner(subagent, event_bus=self.event_bus)
            
            # Execute subagent completely
            result_message = await sub_executor.arun()
            return f"Result from {target_agent_id}:\n{result_message.message.content}"
            
        delegate_tool = HostTool(
            name="delegate_task",
            description="Delegate a sub-task to a specialized subagent, wait for their response, and use it to continue your work.",
            func=_delegate_func,
            schema={
                "type": "function",
                "function": {
                    "name": "delegate_task",
                    "description": "Delegate a sub-task to a specialized subagent, wait for their response, and use it to continue your work.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_agent_id": {
                                "type": "string",
                                "enum": available_agent_ids,
                                "description": "The ID of the agent to delegate the task to."
                            },
                            "task": {
                                "type": "string",
                                "description": "Highly detailed instructions for the subagent."
                            }
                        },
                        "required": ["target_agent_id", "task"]
                    }
                }
            }
        )
        
        # Parallel Delegate Tool
        async def _parallel_delegate_func(target_agent_id: str, tasks: List[str]) -> str:
            async def run_single(task: str, idx: int):
                subagent = await self.subagent_factory(target_agent_id)
                if not subagent:
                    return f"Error: Subagent {target_agent_id} not found."
                    
                # Deterministic isolated planning session with index for parallel clones
                subagent.session_id = f"{agent.session_id}_{target_agent_id}_{idx}"
                
                subagent.add_message(Message(role="user", content=task))
                sub_executor = AgentRunner(subagent, event_bus=self.event_bus)
                result_message = await sub_executor.arun()
                return f"Task: {task}\nResult: {result_message.message.content}\n"
                
            results = await asyncio.gather(*[run_single(t, idx) for idx, t in enumerate(tasks)])
            combined = "\n---\n".join(results)
            return f"Parallel Results from {target_agent_id}:\n{combined}"

        parallel_delegate_tool = HostTool(
            name="parallel_delegate_task",
            description="Delegate MULTIPLE independent sub-tasks to multiple clones of the same subagent to run concurrently.",
            func=_parallel_delegate_func,
            schema={
                "type": "function",
                "function": {
                    "name": "parallel_delegate_task",
                    "description": "Delegate MULTIPLE independent sub-tasks to multiple clones of the same subagent to run concurrently.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "target_agent_id": {
                                "type": "string",
                                "enum": available_agent_ids,
                                "description": "The ID of the agent to delegate the tasks to."
                            },
                            "tasks": {
                                "type": "array",
                                "items": {"type": "string"},
                                "description": "List of independent tasks to run concurrently."
                            }
                        },
                        "required": ["target_agent_id", "tasks"]
                    }
                }
            }
        )
        
        # Inject tools if not already present
        agent_tool_names = [t.name for t in agent.tools]
        if "handoff_to_agent" not in agent_tool_names:
            agent.tools.append(handoff_tool)
        if "delegate_task" not in agent_tool_names:
            agent.tools.append(delegate_tool)
        if "parallel_delegate_task" not in agent_tool_names:
            agent.tools.append(parallel_delegate_tool)

    async def arun(self, user_input: Optional[str] = None, subagents_info: List[Dict[str, Any]] = []) -> Message:
        """
        Run the swarm. Starts with the Leader, but can hand off control dynamically.
        """
        if user_input:
            self.current_agent.add_message(Message(role="user", content=user_input))
            
        while True:
            self._inject_swarm_tools(self.current_agent, subagents_info)
            executor = AgentRunner(self.current_agent, event_bus=self.event_bus)
            
            try:
                # Run the current agent until it completes or throws a HandoffException
                final_response = await executor.arun()
                return final_response
                
            except HandoffException as e:
                # The agent decided to hand off control completely
                print(f"[Swarm Handoff] {self.current_agent.id} -> {e.target_agent_id} (Reason: {e.reason})")
                
                # Fetch the new agent
                next_agent = await self.subagent_factory(e.target_agent_id)
                if not next_agent:
                    # If target is invalid, tell the current agent it failed and loop again
                    self.current_agent.add_message(Message(
                        role="system", 
                        content=f"Handoff failed: Agent {e.target_agent_id} does not exist. Please try again or answer the user directly."
                    ))
                    continue
                    
                # Handoff success: The new agent becomes the primary driver
                # Pass any context the original agent deemed necessary
                if e.context:
                    context_str = "\n".join([f"{k}: {v}" for k,v in e.context.items()])
                    next_agent.add_message(Message(
                        role="system",
                        content=f"You have been handed control of the conversation. Context provided:\n{context_str}"
                    ))
                    
                # If there are previous user messages, copy them over so the new agent has chat history
                # (Optional depending on how strict isolation should be for handoffs)
                user_msgs = [m for m in self.current_agent.messages if m.role == "user"]
                for um in user_msgs:
                    if um not in next_agent.messages:
                        next_agent.add_message(um)
                        
                self.current_agent = next_agent
