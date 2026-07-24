import asyncio
import os
import logging
import sqlalchemy
from sqlalchemy.orm import sessionmaker
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.core.messages import Message
from orkestra.core.agent import Agent
from orkestra.workflows.runner import AgentRunner
from orkestra.core.context import TokenSummarizationStrategy
from orkestra.memory.postgres import PostgresMemoryStore, MessageModel

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

async def main():
    api_key = os.getenv("GEMINI_API_KEY", "YOUR_API_KEY_HERE")
    provider = GeminiProvider(model_name="gemini-2.5-flash", api_key=api_key)
    
    db_url = "postgresql://orkestra:orkestra@localhost:5432/orkestra"
    try:
        memory = PostgresMemoryStore(db_url)
    except Exception as e:
        print(f"Make sure Postgres is running: {e}")
        return
        
    await memory.aclear("summary_session_pg")
    
    strategy = TokenSummarizationStrategy(max_tokens=25, provider=provider)
    
    agent = Agent(
        name="SummaryBot",
        description="A bot.",
        system_prompt="You are a helpful assistant.",
        provider=provider,
        memory=memory,
        session_id="summary_session_pg",
        compaction=strategy
    )
    
    runner = AgentRunner(agent)
    
    # 3 messages to trigger compaction
    msg1 = "Hello! My name is Alex. I am a software engineer."
    await agent.aadd_message(Message(role="user", content=msg1))
    await runner.arun()
    
    msg2 = "I also have a pet dog named Max. Max loves playing fetch in central park on Sundays."
    await agent.aadd_message(Message(role="user", content=msg2))
    await runner.arun()
    
    msg3 = "By the way, Orkestra uses Postgres for memory management!"
    await agent.aadd_message(Message(role="user", content=msg3))
    
    print("Calling LLM -> Triggers Postgres DB Mutation...")
    await runner.arun()
    
    # Query Postgres directly
    print("\n------------------------------------------------------------------")
    print("RAW ROWS FROM POSTGRESQL TABLE 'orkestra_messages':")
    print("------------------------------------------------------------------")
    
    engine = sqlalchemy.create_engine(db_url)
    Session = sessionmaker(bind=engine)
    session = Session()
    
    rows = session.query(MessageModel).filter_by(session_id="summary_session_pg").order_by(MessageModel.id).all()
    
    for row in rows:
        print(f"ID: {row.id} | ROLE: {row.role:10} | CONTENT: {row.content[:80]}...")

if __name__ == "__main__":
    asyncio.run(main())
