import asyncio
from sqlalchemy.ext.asyncio import create_async_engine
import os

async def run():
    engine = create_async_engine("postgresql+asyncpg://postgres:postgres@localhost:5432/orkestra")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE agents ADD COLUMN max_iterations INTEGER DEFAULT 20"))
        except Exception as e:
            print("max_iterations error:", e)
        try:
            await conn.execute(text("ALTER TABLE agents ADD COLUMN compaction_tokens INTEGER DEFAULT 30000"))
        except Exception as e:
            print("compaction_tokens error:", e)

from sqlalchemy import text
asyncio.run(run())
