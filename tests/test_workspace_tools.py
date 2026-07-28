import pytest
import asyncio
from orkestra.workspace.in_memory import InMemoryWorkspaceStore
from orkestra.workspace.tools import get_planning_tools

@pytest.fixture
def workspace_store():
    return InMemoryWorkspaceStore()

@pytest.mark.asyncio
async def test_planning_tools(workspace_store):
    tools = get_planning_tools("session_1", workspace_store)
    assert len(tools) == 3
    
    # map tools by name
    tool_map = {t.name: t for t in tools}
    create_plan = tool_map["create_plan"]
    update_task = tool_map["update_task"]
    
    # Create plan
    res = await create_plan.func(["task 1", "task 2"])
    assert "successfully" in res
    
    plan = await workspace_store.aget_active_plan("session_1")
    assert plan is not None
    assert len(plan.tasks) == 2
    
    # Update task
    res = await update_task.func(1, "DONE", "finished early")
    assert "updated successfully" in res
    
    plan = await workspace_store.aget_active_plan("session_1")
    assert plan.tasks[0].status == "DONE"
    assert plan.tasks[0].notes == "finished early"
    
    # Auto-archive on all done
    res = await update_task.func(2, "DONE", "finished too")
    assert "auto-archived" in res
    
    # No active plan should exist now
    plan = await workspace_store.aget_active_plan("session_1")
    assert plan is None


