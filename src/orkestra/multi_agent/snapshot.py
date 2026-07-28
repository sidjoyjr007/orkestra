import json
import os
from typing import Dict, Any, Optional
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.multi_agent.scratchpad import SharedScratchpad
from orkestra.core.messages import Message, ToolCall
from orkestra.core.agent import Agent
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.multi_agent.snapshot")

class SnapshotManager:
    """
    Manages saving and restoring checkpoints for a multi-agent workflow.
    """
    def __init__(self, checkpoint_dir: str = ".checkpoints"):
        self.checkpoint_dir = checkpoint_dir
        if not os.path.exists(self.checkpoint_dir):
            os.makedirs(self.checkpoint_dir)

    def _serialize_message(self, msg: Message) -> Dict[str, Any]:
        data = {
            "role": msg.role,
            "content": msg.content,
            "name": msg.name,
            "tool_call_id": msg.tool_call_id,
        }
        if msg.tool_calls:
            data["tool_calls"] = [{"id": tc.id, "function_name": tc.function_name, "function_arguments": tc.function_arguments} for tc in msg.tool_calls]
        return data

    def _deserialize_message(self, data: Dict[str, Any]) -> Message:
        tool_calls = None
        if "tool_calls" in data:
            tool_calls = [ToolCall(id=tc["id"], function_name=tc["function_name"], function_arguments=tc["function_arguments"]) for tc in data["tool_calls"]]
            
        return Message(
            role=data.get("role", "user"),
            content=data.get("content"),
            name=data.get("name"),
            tool_call_id=data.get("tool_call_id"),
            tool_calls=tool_calls
        )

    def save_checkpoint(
        self, 
        checkpoint_id: str, 
        active_agents: Dict[str, Agent], 
        current_agent_name: str, 
        scratchpad: Optional[SharedScratchpad] = None,
        handoff_state: Optional[Dict[str, Any]] = None
    ):
        """Saves the state of all active agents and the scratchpad."""
        state = {
            "current_agent_name": current_agent_name,
            "handoff_state": handoff_state or {},
            "scratchpad": scratchpad.to_dict() if scratchpad else {},
            "agents": {}
        }
        
        for name, agent in active_agents.items():
            state["agents"][name] = {
                "session_id": agent.session_id,
                "messages": [self._serialize_message(m) for m in agent.messages],
                "usage": agent.usage
            }
            
        filepath = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")
        with open(filepath, "w") as f:
            json.dump(state, f, indent=2)
            
    def load_checkpoint(self, checkpoint_id: str, registry: AgentRegistry, scratchpad: Optional[SharedScratchpad] = None) -> Dict[str, Any]:
        """Loads a checkpoint and hydrates the agents."""
        filepath = os.path.join(self.checkpoint_dir, f"{checkpoint_id}.json")
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Checkpoint {checkpoint_id} not found.")
            
        with open(filepath, "r") as f:
            state = json.load(f)
            
        if scratchpad and "scratchpad" in state:
            scratchpad.from_dict(state["scratchpad"])
            
        active_agents = {}
        for name, agent_state in state.get("agents", {}).items():
            template = registry.get_agent(name)
            if template:
                agent = template
                agent.session_id = agent_state.get("session_id", "default")
                agent.messages = [self._deserialize_message(m) for m in agent_state.get("messages", [])]
                agent.usage = agent_state.get("usage", {})
                active_agents[name] = agent
                
        return {
            "current_agent_name": state.get("current_agent_name"),
            "handoff_state": state.get("handoff_state", {}),
            "active_agents": active_agents
        }
        
    def clear_checkpoints(self):
        """Deletes all checkpoint files from the checkpoint directory."""
        if not os.path.exists(self.checkpoint_dir):
            return
            
        for filename in os.listdir(self.checkpoint_dir):
            if filename.endswith(".json"):
                filepath = os.path.join(self.checkpoint_dir, filename)
                try:
                    os.remove(filepath)
                except Exception as e:
                    logger.error(f"Failed to delete checkpoint {filepath}: {e}")
