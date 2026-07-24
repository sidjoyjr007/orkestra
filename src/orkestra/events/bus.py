import asyncio
from typing import Callable, Dict, List, Type
from orkestra.events.base import Event

class EventBus:
    """
    A simple publish-subscribe event bus for routing Orkestra events.
    """
    def __init__(self):
        self._subscribers: Dict[Type[Event], List[Callable]] = {}

    def subscribe(self, event_type: Type[Event], handler: Callable):
        """
        Subscribe a handler function to a specific event type.
        The handler can be synchronous or asynchronous.
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []
        self._subscribers[event_type].append(handler)

    def publish(self, event: Event):
        """
        Publish an event to all subscribers synchronously.
        If a handler is async, it will not be awaited here. 
        Use `apublish` for proper async execution of handlers.
        """
        handlers = []
        for subscribed_type, type_handlers in self._subscribers.items():
            if isinstance(event, subscribed_type):
                handlers.extend(type_handlers)
                
        for handler in handlers:
            handler(event)

    async def apublish(self, event: Event):
        """
        Publish an event to all subscribers asynchronously (fire-and-forget).
        This ensures that slow external event handlers do not block the main Agent loop.
        """
        import logging
        logger = logging.getLogger(__name__)
        
        handlers = []
        for subscribed_type, type_handlers in self._subscribers.items():
            if isinstance(event, subscribed_type):
                handlers.extend(type_handlers)
                
        async def safe_execute(handler, evt):
            try:
                if asyncio.iscoroutinefunction(handler):
                    await handler(evt)
                else:
                    handler(evt)
            except Exception as e:
                logger.error(f"Event handler {handler.__name__} failed for event {type(evt).__name__}: {e}")

        for handler in handlers:
            asyncio.create_task(safe_execute(handler, event))
