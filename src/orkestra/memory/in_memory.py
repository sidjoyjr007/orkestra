from typing import List, Dict
from orkestra.memory.base import BaseMemory
from orkestra.core.messages import Message

class InMemoryStore(BaseMemory):
    """
    A simple in-memory implementation of the BaseMemory interface.
    Stores messages in a Python dictionary. Does not persist across restarts.
    """
    
    def __init__(self):
        # Maps session_id to a list of messages
        self.store: Dict[str, List[Message]] = {}
        # Maps session_id to a serialized state dict
        self.checkpoints: Dict[str, dict] = {}
        
    def add_message(self, session_id: str, message: Message) -> None:
        if session_id not in self.store:
            self.store[session_id] = []
        self.store[session_id].append(message)
        
    def get_messages(self, session_id: str) -> List[Message]:
        return self.store.get(session_id, []).copy()
        
    def clear(self, session_id: str) -> None:
        if session_id in self.store:
            self.store[session_id] = []

    async def aadd_message(self, session_id: str, message: Message) -> None:
        self.add_message(session_id, message)
        
    async def aget_messages(self, session_id: str) -> List[Message]:
        return self.get_messages(session_id)
        
    async def aclear(self, session_id: str) -> None:
        self.clear(session_id)
        
    async def asave_checkpoint(self, session_id: str, state: dict) -> None:
        self.checkpoints[session_id] = state
        
    async def aload_checkpoint(self, session_id: str) -> dict:
        return self.checkpoints.get(session_id, {})
