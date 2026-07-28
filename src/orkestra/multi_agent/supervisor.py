import copy
from typing import List, Optional
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, Response
from orkestra.workflows.runner import AgentRunner
from orkestra.events.bus import EventBus
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.multi_agent.supervisor")

class SupervisedAgent(Agent):
    """
    A specialized Agent wrapper that enforces a Supervisor/Critic review before 
    the task is considered "complete".
    """
    def __init__(
        self,
        worker_agent: Agent,
        critic_agent: Agent,
        max_retries: int = 3
    ):
        self.worker = worker_agent
        self.critic = critic_agent
        self.max_retries = max_retries
        
        # We initialize as a proxy to the worker agent
        super().__init__(
            name=worker_agent.name,
            description=worker_agent.description,
            system_prompt=worker_agent.system_prompt,
            provider=worker_agent.provider,
            tools=worker_agent.tools,
            messages=worker_agent.messages
        )

    def clone(self) -> "SupervisedAgent":
        return SupervisedAgent(
            worker_agent=self.worker.clone(),
            critic_agent=self.critic.clone(),
            max_retries=self.max_retries
        )

    async def aadd_message(self, message: Message):
        await super().aadd_message(message)
        await self.worker.aadd_message(message)

    @property
    def session_id(self) -> str:
        return self.worker.session_id

    @session_id.setter
    def session_id(self, value: str):
        self.worker.session_id = value
        self.critic.session_id = f"{value}_critic"

    @property
    def messages(self) -> List[Message]:
        return self.worker.messages

    @messages.setter
    def messages(self, value: List[Message]):
        self.worker.messages = value

    @property
    def usage(self) -> dict:
        return {
            "prompt_tokens": self.worker.usage.get("prompt_tokens", 0) + self.critic.usage.get("prompt_tokens", 0),
            "completion_tokens": self.worker.usage.get("completion_tokens", 0) + self.critic.usage.get("completion_tokens", 0)
        }

    @usage.setter
    def usage(self, value: dict):
        pass

    async def astep(self, **kwargs) -> Response:
        """
        Overrides the default astep to include the critic loop natively.
        """
        attempt = 0
        last_response = None
        
        while attempt < self.max_retries:
            # 1. Worker generates a response
            last_response = await self.worker.astep(**kwargs)
            worker_msg = last_response.message
            
            # If the worker made a tool call (like handoff), just let it pass through
            if worker_msg.tool_calls:
                # The worker's astep already appended the message to its history
                return last_response
                
            # 2. Critic reviews the response
            critic_prompt = f"""
            You are the Critic. The worker agent has proposed the following response to the user's task.
            Review it carefully.
            
            Worker's Proposed Response:
            {worker_msg.content}
            
            If it is completely correct and fulfills the goal, reply exactly with 'APPROVED'.
            If it is flawed or incomplete, reply with detailed feedback on what needs to be fixed. Do not say APPROVED.
            """
            
            await self.critic.aadd_message(Message(role="user", content=critic_prompt))
            critic_response = await self.critic.astep()
            critic_msg = critic_response.message
            
            if "APPROVED" in critic_msg.content.strip().upper():
                logger.info(f"Critic APPROVED worker {self.worker.name}'s response.")
                return last_response
            else:
                logger.info(f"Critic REJECTED worker {self.worker.name}'s response. Retrying (Attempt {attempt+1}/{self.max_retries})")
                feedback_msg = Message(role="user", content=f"CRITIC FEEDBACK: {critic_msg.content}\nPlease correct your response.")
                
                # Append to the worker's history so it learns
                # The worker's astep already appended the worker_msg to its history, so just add feedback
                await self.worker.aadd_message(feedback_msg)
                
            attempt += 1
            
        logger.warning(f"Worker {self.worker.name} failed to get approval after {self.max_retries} attempts.")
        return last_response
