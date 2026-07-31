from typing import List
from orkestra.core.tools import Tool, HostTool
from orkestra.workspace.base import BaseWorkspaceStore, Plan, Task

def get_planning_tools(session_id: str, workspace: BaseWorkspaceStore) -> List[Tool]:
    
    async def create_plan(tasks: list[str]) -> str:
        """Create a new active plan, archiving any existing active plan."""
        plan = Plan(session_id=session_id, status="ACTIVE")
        for i, t_desc in enumerate(tasks):
            plan.tasks.append(Task(id=i+1, description=t_desc))
        await workspace.asave_plan(plan)
        return "Plan created successfully and set as ACTIVE."
        
    async def batch_update_tasks(updates: list[dict]) -> str:
        """Batch update statuses of tasks (TODO, IN_PROGRESS, DONE, BLOCKED) and add optional notes."""
        plan = await workspace.aget_active_plan(session_id)
        if not plan:
            return "Error: No active plan found."
            
        results = []
        for update in updates:
            task_id = update.get("task_id")
            status = update.get("status")
            notes = update.get("notes", "")
            
            task_found = False
            for t in plan.tasks:
                if t.id == task_id:
                    t.status = status
                    if notes:
                        t.notes = notes
                    task_found = True
                    results.append(f"Task {task_id} updated to {status}.")
                    break
                    
            if not task_found:
                results.append(f"Error: Task {task_id} not found.")
                
        # Auto-archive if all tasks are in a terminal state
        all_done = all(t.status in ["DONE", "FAILED", "BLOCKED"] for t in plan.tasks)
        if all_done:
            plan.status = "ARCHIVED"
            await workspace.asave_plan(plan)
            return "\n".join(results) + "\nAll tasks complete/terminated! Plan has been auto-archived."
            
        await workspace.asave_plan(plan)
        return "\n".join(results)
        
    async def add_task(description: str) -> str:
        """Add a new task to the end of the active plan."""
        plan = await workspace.aget_active_plan(session_id)
        if not plan:
            return "Error: No active plan found."
            
        new_id = len(plan.tasks) + 1
        plan.tasks.append(Task(id=new_id, description=description))
        
        await workspace.asave_plan(plan)
        return f"Task {new_id} added successfully."
        
    return [
        HostTool(
            name="create_plan",
            description="Create a new active plan for the user's request. Pass a list of task descriptions. Hint: Consider the tools listed in YOUR CAPABILITIES and use their exact names or keywords in your tasks to guarantee successful vector DB retrieval later.",
            func=create_plan,
            schema={
                "type": "function",
                "function": {
                    "name": "create_plan",
                    "description": "Create a new active plan.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "items": {"type": "string"}
                            }
                        },
                        "required": ["tasks"]
                    }
                }
            }
        ),
        HostTool(
            name="batch_update_tasks",
            description="Batch update task statuses and add notes. Bundle multiple transitions (e.g. marking one DONE and the next IN_PROGRESS) into a single call. Status must be: TODO, IN_PROGRESS, DONE, or BLOCKED.",
            func=batch_update_tasks,
            schema={
                "type": "function",
                "function": {
                    "name": "batch_update_tasks",
                    "description": "Batch update task statuses and add notes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "updates": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "task_id": {"type": "integer"},
                                        "status": {"type": "string"},
                                        "notes": {"type": "string"}
                                    },
                                    "required": ["task_id", "status"]
                                }
                            }
                        },
                        "required": ["updates"]
                    }
                }
            }
        ),
        HostTool(
            name="add_task",
            description="Add a new task to the end of the active plan.",
            func=add_task,
            schema={
                "type": "function",
                "function": {
                    "name": "add_task",
                    "description": "Add a new task to the end of the active plan.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "description": {"type": "string"}
                        },
                        "required": ["description"]
                    }
                }
            }
        )
    ]
