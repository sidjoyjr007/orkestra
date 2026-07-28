import pytest
import asyncio
from orkestra.workspace.postgres import PostgresWorkspaceStore
from orkestra.workspace.base import Plan

TEST_DB_URL = "sqlite:///test_workspace.db"

@pytest.fixture
def workspace_store():
    # Setup single sqlite DB for the function
    store = PostgresWorkspaceStore(TEST_DB_URL)
    return store

@pytest.mark.asyncio
async def test_save_and_get_plan(workspace_store):
    await workspace_store.initialize()
    plan = Plan(session_id="session_1", tasks=[{"id": "1", "description": "do stuff"}])
    await workspace_store.asave_plan(plan)
    
    retrieved = await workspace_store.aget_active_plan("session_1")
    assert retrieved is not None
    assert retrieved.session_id == "session_1"
    # Actually asave_plan creates a NEW entry. Since we update the plan status to COMPLETED,
    # the OLD plan with ACTIVE status might still be in the DB?
    # Wait, asave_plan explicitly sets the OLD active plan's status to ARCHIVED!
    # So we should retrieve it safely.
    
    # Save a completed plan
    plan.status = "COMPLETED"
    await workspace_store.aarchive_active_plan("session_1")
    await workspace_store.asave_plan(plan)
    
    retrieved2 = await workspace_store.aget_active_plan("session_1")
    assert retrieved2 is None
