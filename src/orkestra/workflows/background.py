import asyncio
from orkestra.events.bus import EventBus
from orkestra.events.base import TaskCompletedEvent
from orkestra.core.messages import Message
from orkestra.multi_agent.orchestrator import Orchestrator
from orkestra.multi_agent.registry import AgentRegistry
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.workflows.background")

class WakeupService:
    """
    A service that listens for TaskCompletedEvents and wakes up sleeping agents.
    In a real production system, this could be an HTTP Webhook endpoint.
    """
    def __init__(self, event_bus: EventBus, registry: AgentRegistry, orchestrator: Orchestrator):
        self.event_bus = event_bus
        self.registry = registry
        self.orchestrator = orchestrator
        
        # Subscribe to completion events
        self.event_bus.subscribe(TaskCompletedEvent, self._handle_task_completed)
        logger.info("WakeupService initialized and listening for TaskCompletedEvents.")

    async def _handle_task_completed(self, event: TaskCompletedEvent):
        """
        Triggered when a background task finishes.
        1. Finds the sleeping agent.
        2. Appends the tool result to its memory.
        3. Boots up the Orchestrator to resume the agent's run loop.
        """
        logger.info(f"WakeupService received completion for task {event.tool_call_id} (Session: {event.session_id})")
        
        agent = self.registry.get_agent(event.agent_name)
        if not agent:
            logger.error(f"Cannot wake up agent '{event.agent_name}': Not found in registry.")
            return

        # 1. Inject the result into memory as if the tool just finished synchronously
        # Need to temporarily set the session_id to write to the correct db namespace
        original_session = agent.session_id
        agent.session_id = event.session_id
        
        result_msg = Message(
            role="tool", 
            content=event.result, 
            tool_call_id=event.tool_call_id
        )
        await agent.aadd_message(result_msg)
        
        # 2. Boot up the Orchestrator for this specific session
        logger.info(f"Waking up agent '{event.agent_name}' to process background result.")
        
        # We run the orchestrator in the background to not block the event bus listener
        asyncio.create_task(self.orchestrator.arun(
            entry_agent_name=event.agent_name, 
            session_id=event.session_id, 
            max_turns=5
        ))
        
        agent.session_id = original_session
