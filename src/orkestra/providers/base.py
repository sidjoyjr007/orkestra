import abc
from typing import Any, AsyncIterator, Dict, Iterator, List, Optional
from orkestra.core.messages import Message, Response, ResponseChunk

class BaseProvider(abc.ABC):
    """Abstract base class for all LLM providers."""

    def __init__(self, model_name: str, api_key: Optional[str] = None, event_bus: Optional[Any] = None, **kwargs):
        self.model_name = model_name
        self.api_key = api_key
        self.event_bus = event_bus
        self.config = kwargs

    @abc.abstractmethod
    def generate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Response:
        """
        Generate a complete non-streaming response.
        """
        pass

    @abc.abstractmethod
    def generate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Iterator[ResponseChunk]:
        """
        Generate a streaming response.
        """
        pass

    @abc.abstractmethod
    async def agenerate(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> Response:
        """
        Asynchronously generate a complete non-streaming response.
        """
        pass

    @abc.abstractmethod
    async def agenerate_stream(
        self,
        messages: List[Message],
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        tools: Optional[List[Dict[str, Any]]] = None,
        **kwargs
    ) -> AsyncIterator[ResponseChunk]:
        """
        Asynchronously generate a streaming response.
        """
        pass
