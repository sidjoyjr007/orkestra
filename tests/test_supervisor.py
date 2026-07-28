import pytest
from unittest.mock import AsyncMock, MagicMock
from orkestra.core.agent import Agent
from orkestra.core.messages import Message, Response
from orkestra.multi_agent.supervisor import SupervisedAgent

@pytest.mark.asyncio
async def test_supervised_agent_approval():
    worker = Agent(name="worker", description="w", system_prompt="w", provider=MagicMock())
    critic = Agent(name="critic", description="c", system_prompt="c", provider=MagicMock())
    
    worker.astep = AsyncMock(return_value=Response(message=Message(role="assistant", content="Here is the report"), usage={}))
    critic.astep = AsyncMock(return_value=Response(message=Message(role="assistant", content="APPROVED"), usage={}))
    
    supervised = SupervisedAgent(worker_agent=worker, critic_agent=critic, max_retries=3)
    
    res = await supervised.astep()
    
    assert res.message.content == "Here is the report"
    assert worker.astep.call_count == 1
    assert critic.astep.call_count == 1

@pytest.mark.asyncio
async def test_supervised_agent_rejection_and_retry():
    worker = Agent(name="worker", description="w", system_prompt="w", provider=MagicMock())
    critic = Agent(name="critic", description="c", system_prompt="c", provider=MagicMock())
    
    # Worker generates bad then good
    worker.astep = AsyncMock(side_effect=[
        Response(message=Message(role="assistant", content="Bad report"), usage={}),
        Response(message=Message(role="assistant", content="Good report"), usage={})
    ])
    
    # Critic rejects then approves
    critic.astep = AsyncMock(side_effect=[
        Response(message=Message(role="assistant", content="Fix the formatting"), usage={}),
        Response(message=Message(role="assistant", content="APPROVED"), usage={})
    ])
    
    supervised = SupervisedAgent(worker_agent=worker, critic_agent=critic, max_retries=3)
    
    res = await supervised.astep()
    
    assert res.message.content == "Good report"
    assert worker.astep.call_count == 2
    assert critic.astep.call_count == 2
    
    # Check if feedback was added to worker's history
    assert len(worker.messages) >= 1
    assert "CRITIC FEEDBACK: Fix the formatting" in worker.messages[-1].content
