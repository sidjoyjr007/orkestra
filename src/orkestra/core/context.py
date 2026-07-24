import abc
from typing import List, Any
import json
from orkestra.core.messages import Message
from orkestra.core.prompts import SUMMARIZATION_PROMPT

class CompactionStrategy(abc.ABC):
    @abc.abstractmethod
    async def aprocess(self, messages: List[Message], system_prompt: str, memory: Any, session_id: str) -> List[Message]:
        pass

class KeepAllStrategy(CompactionStrategy):
    async def aprocess(self, messages: List[Message], system_prompt: str, memory: Any, session_id: str) -> List[Message]:
        if messages and messages[0].role == "system":
            return [Message(role="system", content=system_prompt)] + messages[1:]
        return [Message(role="system", content=system_prompt)] + messages

class SlidingWindowStrategy(CompactionStrategy):
    def __init__(self, max_messages: int):
        self.max_messages = max_messages
        
    async def aprocess(self, messages: List[Message], system_prompt: str, memory: Any, session_id: str) -> List[Message]:
        # Filter out system messages from the count
        non_system = [m for m in messages if m.role != "system"]
        
        if len(non_system) > self.max_messages:
            non_system = non_system[-self.max_messages:]
            
        return [Message(role="system", content=system_prompt)] + non_system

class TokenSummarizationStrategy(CompactionStrategy):
    def __init__(self, max_tokens: int, provider: Any):
        self.max_tokens = max_tokens
        self.provider = provider
        
    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4
        
    def _count_message_tokens(self, messages: List[Message]) -> int:
        total = 0
        for m in messages:
            if m.content:
                total += self._estimate_tokens(m.content)
            if m.tool_calls:
                total += sum(self._estimate_tokens(json.dumps(tc.function_arguments)) for tc in m.tool_calls)
        return total

    async def aprocess(self, messages: List[Message], system_prompt: str, memory: Any, session_id: str) -> List[Message]:
        non_system = [m for m in messages if m.role != "system"]
        
        current_tokens = self._count_message_tokens(non_system)
        if current_tokens <= self.max_tokens or len(non_system) < 4:
            return [Message(role="system", content=system_prompt)] + non_system
            
        # We need to summarize. Let's keep the last 2 messages (e.g., user prompt and current state)
        keep_recent = 2
        to_summarize = non_system[:-keep_recent]
        recent = non_system[-keep_recent:]
        
        # Build prompt for summarization
        conv_text = "\n\n".join([f"{m.role}: {m.content or 'Tool Calls: ' + str(m.tool_calls)}" for m in to_summarize])
        
        summary_request = [
            Message(role="system", content=SUMMARIZATION_PROMPT),
            Message(role="user", content=conv_text)
        ]
        
        # Call provider
        response = await self.provider.agenerate(summary_request)
        summary_text = response.message.content
        
        summary_msg = Message(
            role="system", 
            content=f"Summary of previous conversation: {summary_text}"
        )
        
        # Mutate database! 
        # Since memory might just have append/clear, we clear and re-add.
        if memory:
            await memory.aclear(session_id)
            await memory.aadd_message(session_id, summary_msg)
            for m in recent:
                await memory.aadd_message(session_id, m)
                
        return [Message(role="system", content=system_prompt), summary_msg] + recent
