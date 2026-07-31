from orkestra.events.bus import EventBus
from orkestra.events.base import AgentStepStarted, ToolExecutionStarted, TokenUsageReported
from backend.core.logging import get_logger

logger = get_logger("orkestra.telemetry")

class TelemetryBridge:
    """
    Subscribes to Orkestra's internal EventBus and forwards critical telemetry 
    to the structured logger and metrics systems.
    """
    def __init__(self, event_bus: EventBus):
        self.event_bus = event_bus
        self._setup_subscriptions()
        logger.info("telemetry_bridge_initialized")

    def _setup_subscriptions(self):
        # We can safely use sync wrappers around the async handlers if needed, 
        # or use async handlers directly since EventBus.apublish handles awaitables.
        self.event_bus.subscribe(AgentStepStarted, self._on_agent_started)
        self.event_bus.subscribe(ToolExecutionStarted, self._on_tool_started)
        self.event_bus.subscribe(TokenUsageReported, self._on_token_usage)

    async def _on_agent_started(self, event: AgentStepStarted):
        logger.info(
            "agent_step_started",
            agent_name=event.agent_name,
            session_id=event.session_id,
        )

    async def _on_tool_started(self, event: ToolExecutionStarted):
        logger.info(
            "tool_execution_started",
            agent_name=event.agent_name,
            session_id=event.session_id,
            tool_name=event.tool_name,
            tool_call_id=event.tool_call_id
        )

    async def _on_token_usage(self, event: TokenUsageReported):
        logger.info(
            "token_usage_reported",
            agent_name=event.agent_name,
            session_id=event.session_id,
            prompt_tokens=event.prompt_tokens,
            completion_tokens=event.completion_tokens,
            total_tokens=event.total_tokens,
            model=event.model
        )
