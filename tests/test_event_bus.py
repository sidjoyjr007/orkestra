import pytest
import asyncio
from unittest.mock import MagicMock, AsyncMock
from orkestra.events.bus import EventBus
from orkestra.events.base import Event

from dataclasses import dataclass

@dataclass
class DummyEvent(Event):
    agent_name: str

@dataclass
class SubEvent(DummyEvent):
    pass
    
def test_event_bus_sync_publish():
    bus = EventBus()
    handler = MagicMock()
    bus.subscribe(DummyEvent, handler)
    
    event = DummyEvent(agent_name="test")
    bus.publish(event)
    
    handler.assert_called_once_with(event)

def test_event_bus_subclass():
    bus = EventBus()
    handler = MagicMock()
    bus.subscribe(DummyEvent, handler)
    
    event = SubEvent(agent_name="test")
    bus.publish(event)
    
    handler.assert_called_once_with(event)

@pytest.mark.asyncio
async def test_event_bus_async_publish():
    bus = EventBus()
    
    sync_handler = MagicMock()
    async_handler = AsyncMock()
    
    # We must define an AsyncMock compatible function to check if it gets called properly
    called = []
    
    async def amock(event):
        called.append("async")
        
    def smock(event):
        called.append("sync")
        
    bus.subscribe(DummyEvent, amock)
    bus.subscribe(DummyEvent, smock)
    
    event = DummyEvent(agent_name="test")
    await bus.apublish(event)
    
    # Let tasks run
    await asyncio.sleep(0.01)
    
    assert "async" in called
    assert "sync" in called

@pytest.mark.asyncio
async def test_event_bus_error_handling(caplog):
    bus = EventBus()
    
    def failing_handler(event):
        raise ValueError("Simulated failure")
        
    bus.subscribe(DummyEvent, failing_handler)
    event = DummyEvent(agent_name="test")
    
    # Should not raise exception
    await bus.apublish(event)
    await asyncio.sleep(0.01)
    
    assert "Simulated failure" in caplog.text
