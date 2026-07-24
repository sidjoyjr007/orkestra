from abc import ABC, abstractmethod
from typing import List
from orkestra.core.messages import Message

class BaseMemory(ABC):
    """
    Abstract base class for Orkestra memory providers.
    
    Memory providers are responsible for persisting and retrieving 
    an agent's conversation history across sessions.
    """
    
    @abstractmethod
    def add_message(self, session_id: str, message: Message) -> None:
        """
        Add a single message to the specified session.
        """
        pass
        
    @abstractmethod
    def get_messages(self, session_id: str) -> List[Message]:
        """
        Retrieve all messages for a given session.
        """
        pass
        
    @abstractmethod
    def clear(self, session_id: str) -> None:
        """
        Clear all messages for a given session.
        """
        pass
        
    @abstractmethod
    async def aadd_message(self, session_id: str, message: Message) -> None:
        """
        Asynchronously add a single message to the specified session.
        """
        pass
        
    @abstractmethod
    async def aget_messages(self, session_id: str) -> List[Message]:
        """
        Asynchronously retrieve all messages for a given session.
        """
        pass
        
    @abstractmethod
    async def aclear(self, session_id: str) -> None:
        """
        Asynchronously clear all messages for a given session.
        """
        pass

    @abstractmethod
    async def asave_checkpoint(self, session_id: str, state: dict) -> None:
        """
        Asynchronously save a serialized checkpoint of the agent state.
        """
        pass
        
    @abstractmethod
    async def aload_checkpoint(self, session_id: str) -> dict:
        """
        Asynchronously load a serialized checkpoint of the agent state.
        Returns empty dict if no checkpoint exists.
        """
        pass
