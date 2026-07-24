import pytest
from orkestra.workspace.in_memory import InMemoryWorkspaceStore
from orkestra.workspace.base import Plan, Task
from orkestra.workspace.tools import get_planning_tools

@pytest.mark.asyncio
async def test_workspace_lifecycle():
    store = InMemoryWorkspaceStore()
    
    # 1. Start with no plan
    plan = await store.aget_active_plan("session_1")
    assert plan is None
    
    # 2. Inject and use tools
    tools = get_planning_tools("session_1", store)
    create_tool = next(t for t in tools if t.name == "create_plan")
    
    await create_tool.func(["Task A", "Task B"])
    
    active_plan = await store.aget_active_plan("session_1")
    assert active_plan is not None
    assert active_plan.status == "ACTIVE"
    assert len(active_plan.tasks) == 2
    assert active_plan.tasks[0].description == "Task A"
    assert active_plan.tasks[0].status == "TODO"
    
    # 3. Update task
    update_tool = next(t for t in tools if t.name == "update_task")
    await update_tool.func(1, "IN_PROGRESS", "Working on it")
    
    active_plan = await store.aget_active_plan("session_1")
    assert active_plan.tasks[0].status == "IN_PROGRESS"
    assert active_plan.tasks[0].notes == "Working on it"
    
    # 4. Finish all tasks (auto archive)
    await update_tool.func(1, "DONE", "Done A")
    await update_tool.func(2, "DONE", "Done B")
    
    # The plan should now be auto-archived, so get_active_plan returns None
    active_plan = await store.aget_active_plan("session_1")
    assert active_plan is None
    
    # 5. Verify it's archived in the store
    assert len(store.plans["session_1"]) == 1
    assert store.plans["session_1"][0].status == "ARCHIVED"
