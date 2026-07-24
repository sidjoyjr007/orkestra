from typing import List
from orkestra.core.tools import Tool
from orkestra.workspace.base import BaseWorkspaceStore, Plan, Task

def get_planning_tools(session_id: str, workspace: BaseWorkspaceStore) -> List[Tool]:
    
    async def create_plan(tasks: List[str]) -> str:
        """Create a new active plan, archiving any existing active plan."""
        plan = Plan(session_id=session_id, status="ACTIVE")
        for i, t_desc in enumerate(tasks):
            plan.tasks.append(Task(id=i+1, description=t_desc))
        await workspace.asave_plan(plan)
        return "Plan created successfully and set as ACTIVE."
        
    async def update_task(task_id: int, status: str, notes: str = "") -> str:
        """Update the status of an existing task (TODO, IN_PROGRESS, DONE, BLOCKED) and add optional notes."""
        plan = await workspace.aget_active_plan(session_id)
        if not plan:
            return "Error: No active plan found."
            
        task_found = False
        for t in plan.tasks:
            if t.id == task_id:
                t.status = status
                if notes:
                    t.notes = notes
                task_found = True
                break
                
        if not task_found:
            return f"Error: Task {task_id} not found in the active plan."
            
        # Auto-archive if all tasks are done
        all_done = all(t.status == "DONE" for t in plan.tasks)
        if all_done:
            plan.status = "ARCHIVED"
            await workspace.asave_plan(plan)
            return f"Task {task_id} updated. All tasks complete! Plan has been auto-archived."
            
        await workspace.asave_plan(plan)
        return f"Task {task_id} updated successfully to {status}."
        
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
        Tool(
            name="create_plan",
            description="Create a new active plan for the user's request. Pass a list of task descriptions.",
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
        Tool(
            name="update_task",
            description="Update a task's status and add notes. Use this when you start or finish a task. Status must be: TODO, IN_PROGRESS, DONE, or BLOCKED.",
            func=update_task,
            schema={
                "type": "function",
                "function": {
                    "name": "update_task",
                    "description": "Update a task's status and add notes.",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "task_id": {"type": "integer"},
                            "status": {"type": "string"},
                            "notes": {"type": "string"}
                        },
                        "required": ["task_id", "status"]
                    }
                }
            }
        ),
        Tool(
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
