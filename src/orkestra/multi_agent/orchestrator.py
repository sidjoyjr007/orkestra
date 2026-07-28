import asyncio
from typing import Dict, Any, Optional, List
from dataclasses import dataclass

@dataclass
class WorkflowResult:
    final_agent_name: str
    total_turns: int
    total_usage: Dict[str, int]

from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.events.bus import EventBus
from orkestra.events.base import HandoffRequested
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.multi_agent.handoff import DynamicHandoffTool
from orkestra.multi_agent.subagent import DynamicSubAgentTool, DynamicParallelSubAgentTool
from orkestra.multi_agent.scratchpad import SharedScratchpad, ReadScratchpadTool, WriteScratchpadTool
from orkestra.multi_agent.snapshot import SnapshotManager
from orkestra.core.exceptions import WorkflowPausedError, HandoffException
from orkestra.core.messages import Message
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.multi_agent.orchestrator")

class Orchestrator:
    """
    A multi-agent runner that manages execution and handles handoff events natively.
    """
    def __init__(self, registry: AgentRegistry, event_bus: EventBus, scratchpad: Optional[SharedScratchpad] = None, checkpoint_dir: Optional[str] = None):
        self.registry = registry
        self.event_bus = event_bus
        self.scratchpad = scratchpad
        self.active_agent: Optional[Agent] = None
        self.active_agents_dict: Dict[str, Agent] = {}
        
        self.snapshot_manager = SnapshotManager(checkpoint_dir) if checkpoint_dir else None
        
        # Graph Topology
        self.handoff_edges: Dict[str, List[str]] = {}
        self.delegation_edges: Dict[str, List[str]] = {}
        
        # Handoff state
        self._handoff_target: Optional[str] = None
        self._handoff_context: Optional[str] = None
        self._handoff_tool_call_id: Optional[str] = None

    def add_handoff_edge(self, source: str, target: str):
        """Define that the source agent is allowed to handoff to the target agent."""
        if source not in self.handoff_edges:
            self.handoff_edges[source] = []
        if target not in self.handoff_edges[source]:
            self.handoff_edges[source].append(target)

    def add_delegation_edge(self, source: str, target: str):
        """Define that the source agent is allowed to delegate to the target sub-agent."""
        if source not in self.delegation_edges:
            self.delegation_edges[source] = []
        if target not in self.delegation_edges[source]:
            self.delegation_edges[source].append(target)

    def is_graph_mode(self) -> bool:
        """Returns True if any edges have been defined, enabling strict routing."""
        return len(self.handoff_edges) > 0 or len(self.delegation_edges) > 0

    async def resume(self, checkpoint_id: str, max_turns: int = 10) -> WorkflowResult:
        if not self.snapshot_manager:
            raise ValueError("Cannot resume without a configured checkpoint_dir")
            
        state = self.snapshot_manager.load_checkpoint(checkpoint_id, self.registry, self.scratchpad)
        self.active_agents_dict = state["active_agents"]
        self._handoff_target = state["handoff_state"].get("target")
        self._handoff_context = state["handoff_state"].get("context")
        self._handoff_tool_call_id = state["handoff_state"].get("tool_call_id")
        
        entry_agent_name = state["current_agent_name"]
        return await self._arun_loop(entry_agent_name, "resumed_session", max_turns)

    async def arun(self, entry_agent_name: str, session_id: str = "default_session", max_turns: int = 10) -> WorkflowResult:
        """
        Runs the multi-agent system, dynamically hot-swapping agents as handoffs occur.
        """
        logger.info(f"Starting Multi-Agent Orchestrator with entry point: {entry_agent_name}")
        return await self._arun_loop(entry_agent_name, session_id, max_turns)

    async def _arun_loop(self, entry_agent_name: str, session_id: str, max_turns: int) -> WorkflowResult:
        current_agent_name = entry_agent_name
        
        for turn in range(max_turns):
            if current_agent_name in self.active_agents_dict:
                self.active_agent = self.active_agents_dict[current_agent_name]
            else:
                self.active_agent = self.registry.get_agent(current_agent_name)
                if self.active_agent:
                    self.active_agent.session_id = session_id
                    self.active_agents_dict[current_agent_name] = self.active_agent
            
            # If we just arrived here via handoff, inject the context into the active agent's memory
            if self._handoff_context and self._handoff_tool_call_id:
                # We need to acknowledge the handoff in the previous agent's memory, 
                # but since we are isolated, we just inject the handoff instructions as a system/user message 
                # into the NEW agent.
                context_msg = Message(
                    role="user", 
                    content=f"SYSTEM NOTIFICATION: You have been handed control of the workflow. Context from previous agent: {self._handoff_context}"
                )
                await self.active_agent.aadd_message(context_msg)
                
                # Clear handoff state
                self._handoff_context = None
                self._handoff_tool_call_id = None
                self._handoff_target = None
                
            # Auto-inject DynamicHandoffTool, DynamicSubAgentTool, and DynamicParallelSubAgentTool
            # Remove any existing dynamic tools to avoid duplicates
            self.active_agent.tools = [t for t in self.active_agent.tools if t.name not in ["handoff_to_agent", "delegate_to_subagent", "delegate_parallel_subagents", "read_scratchpad", "write_scratchpad"]]
            
            if self.is_graph_mode():
                # STRICT GRAPH MODE: Only allow targets defined in edges
                allowed_handoffs = self.handoff_edges.get(self.active_agent.name, [])
                allowed_delegations = self.delegation_edges.get(self.active_agent.name, [])
            else:
                # SWARM MODE: Allow any agent to route to any other agent
                all_agents = [name for name in self.registry.list_agents() if name != self.active_agent.name]
                allowed_handoffs = all_agents
                allowed_delegations = all_agents
                
            if allowed_handoffs:
                dynamic_handoff = DynamicHandoffTool(
                    available_agents=allowed_handoffs,
                    event_bus=self.event_bus,
                    source_agent_name=self.active_agent.name
                )
                self.active_agent.tools.append(dynamic_handoff)
                
            if allowed_delegations:
                dynamic_subagent = DynamicSubAgentTool(
                    available_agents=allowed_delegations,
                    registry=self.registry,
                    event_bus=self.event_bus,
                    manager_agent_name=self.active_agent.name,
                    parent_session_id=session_id
                )
                self.active_agent.tools.append(dynamic_subagent)
                
                dynamic_parallel_subagent = DynamicParallelSubAgentTool(
                    available_agents=allowed_delegations,
                    registry=self.registry,
                    event_bus=self.event_bus,
                    manager_agent_name=self.active_agent.name,
                    parent_session_id=session_id
                )
                self.active_agent.tools.append(dynamic_parallel_subagent)
                
            if self.scratchpad is not None:
                self.active_agent.tools.append(ReadScratchpadTool(self.scratchpad))
                self.active_agent.tools.append(WriteScratchpadTool(self.scratchpad))
                
            runner = AgentRunner(agent=self.active_agent, event_bus=self.event_bus)
            
            logger.info(f"--- Multi-Agent Turn {turn+1}: Control handed to {self.active_agent.name} ---")
            
            try:
                # Run the active agent until it finishes its task or raises WorkflowPausedError (handoff/HITL)
                await runner.arun()
            except HandoffException as e:
                logger.info(f"Handoff intercepted natively: {self.active_agent.name} -> {e.target_agent_name}")
                self._handoff_target = e.target_agent_name
                self._handoff_context = e.context_message
                self._handoff_tool_call_id = e.tool_call_id
            except WorkflowPausedError as e:
                logger.info(f"Runner for {self.active_agent.name} paused for HITL: {e}")
                raise e # Bubble up to the caller to handle the pause
                
            # Check if a handoff was requested during that run
            if self._handoff_target:
                logger.info(f"Executing Handoff: {self.active_agent.name} -> {self._handoff_target}")
                
                if self.snapshot_manager:
                    self.snapshot_manager.save_checkpoint(
                        checkpoint_id=f"handoff_{turn}",
                        active_agents=self.active_agents_dict,
                        current_agent_name=self._handoff_target,
                        scratchpad=self.scratchpad,
                        handoff_state={
                            "target": self._handoff_target,
                            "context": self._handoff_context,
                            "tool_call_id": self._handoff_tool_call_id
                        }
                    )
                
                # Resolve the handoff tool call in the source agent so it isn't left hanging
                if self._handoff_tool_call_id:
                    await self.active_agent.aadd_message(
                        Message(role="tool", name=f"handoff_to_{self._handoff_target}", content="Handoff successful. You are now asleep.", tool_call_id=self._handoff_tool_call_id)
                    )
                    
                current_agent_name = self._handoff_target
                continue # Loop restarts with new active agent
            else:
                # If no handoff was requested, the workflow naturally completed or is waiting for human input
                logger.info("No handoff requested. Multi-Agent workflow sleeping/complete.")
                break
                
        # Aggregate token usage across all agents in the registry that participated
        total_prompt_tokens = 0
        total_completion_tokens = 0
        
        for agent in self.active_agents_dict.values():
            total_prompt_tokens += agent.usage.get("prompt_tokens", 0)
            total_completion_tokens += agent.usage.get("completion_tokens", 0)
                
        return WorkflowResult(
            final_agent_name=current_agent_name,
            total_turns=turn + 1,
            total_usage={"prompt_tokens": total_prompt_tokens, "completion_tokens": total_completion_tokens}
        )
