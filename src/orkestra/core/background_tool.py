import asyncio
import inspect
from typing import Any, Callable, Coroutine
from orkestra.core.tools import Tool
from orkestra.events.bus import EventBus
from orkestra.events.base import TaskCompletedEvent
from orkestra.core.exceptions import WorkflowPausedError
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.core.background_tool")

class BackgroundTool(Tool):
    """
    A tool that executes a slow function in the background and immediately pauses the agent.
    
    When this tool is called, it:
    1. Fires the heavy task into a background asyncio task.
    2. Raises a WorkflowPausedError to suspend the AgentRunner.
    3. The background task, when complete, emits a TaskCompletedEvent.
    """
    def __init__(self, name: str, description: str, target_coroutine: Callable[..., Coroutine], event_bus: EventBus):
        # Dynamically build the parameters schema based on the target coroutine's signature
        sig = inspect.signature(target_coroutine)
        parameters = {
            "type": "object",
            "properties": {},
            "required": []
        }
        for param_name, param in sig.parameters.items():
            param_type = "string" # Default
            if param.annotation == int:
                param_type = "integer"
            elif param.annotation == float:
                param_type = "number"
            elif param.annotation == bool:
                param_type = "boolean"
                
            parameters["properties"][param_name] = {"type": param_type}
            if param.default == inspect.Parameter.empty:
                parameters["required"].append(param_name)

        schema = {
            "type": "function",
            "function": {
                "name": name,
                "description": description,
                "parameters": parameters
            }
        }

        super().__init__(name=name, description=description, func=target_coroutine, schema=schema)
        self.target_coroutine = target_coroutine
        self.event_bus = event_bus

    async def arun(self, **kwargs) -> str:
        """
        Intercepts the run call. Instead of returning a string, we launch the task and raise.
        NOTE: In a real system, we'd need session_id and tool_call_id. 
        We rely on the Executor to inject these via kwargs if available, or we fetch them from context.
        For this prototype, we'll expect the caller (ToolExecutor) to inject them.
        """
        session_id = kwargs.pop("_session_id", "default_session")
        tool_call_id = kwargs.pop("_tool_call_id", "unknown_tool_call")
        agent_name = kwargs.pop("_agent_name", "UnknownAgent")

        # Define the wrapper that will run in the background
        async def background_task_wrapper():
            try:
                logger.info(f"Background task '{self.name}' started for session {session_id}")
                result = await self.target_coroutine(**kwargs)
                logger.info(f"Background task '{self.name}' completed for session {session_id}")
            except Exception as e:
                result = f"Error in background task: {str(e)}"
                logger.error(result)
            
            # Fire the event when done
            await self.event_bus.apublish(TaskCompletedEvent(
                agent_name=agent_name,
                session_id=session_id,
                tool_call_id=tool_call_id,
                result=str(result)
            ))

        # 1. Fire and forget
        asyncio.create_task(background_task_wrapper())

        # 2. Kill the agent loop immediately
        raise WorkflowPausedError(f"Sleeping. Awaiting background completion of {self.name}.")
