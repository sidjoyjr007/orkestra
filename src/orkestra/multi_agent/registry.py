from typing import Dict, Optional
from orkestra.core.agent import Agent
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.multi_agent.registry")

class AgentRegistry:
    """
    A central directory for discovering and retrieving agents in a multi-agent system.
    """
    def __init__(self):
        self._agents: Dict[str, Agent] = {}

    def register(self, agent: Agent):
        """Register an agent with the registry."""
        if agent.name in self._agents:
            logger.warning(f"Overwriting existing agent registration for '{agent.name}'")
        self._agents[agent.name] = agent
        logger.debug(f"Registered agent '{agent.name}'")

    def get_agent(self, name: str) -> Optional[Agent]:
        """Retrieve a fresh clone of an agent by name."""
        agent = self._agents.get(name)
        if agent:
            return agent.clone()
        return None

    def list_agents(self) -> list[str]:
        """List all registered agent names."""
        return list(self._agents.keys())
