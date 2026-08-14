import os
import sys
import time
import httpx
import asyncio
import json
from datetime import datetime, date
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional, List

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.exceptions import WorkflowPausedError
from orkestra.core.swarm_executor import SwarmExecutor
from orkestra.events.bus import EventBus
from orkestra.events.base import Event, AgentStepStarted, AgentStepCompleted, TokenUsageReported
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.providers.openai_provider import OpenAIProvider
from orkestra.providers.anthropic_provider import AnthropicProvider

SWARM_ID = os.getenv("SWARM_ID")
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://host.docker.internal:8000")
DEPLOYMENT_TOKEN = os.getenv("DEPLOYMENT_TOKEN")
MEMORY_DATABASE_URL = os.getenv("MEMORY_DATABASE_URL", "sqlite:///memory.db")
TOOL_REGISTRY_URL = os.getenv("TOOL_REGISTRY_URL")
WORKSPACE_DB_URL = os.getenv("WORKSPACE_DB_URL")

swarm_executor_instance = None
event_bus = EventBus()
last_request_time = time.time()
IDLE_TIMEOUT_SECONDS = int(os.getenv("IDLE_TIMEOUT_SECONDS", "600"))

class ChatRequest(BaseModel):
    message: Optional[str] = None
    session_id: str
    webhook_url: Optional[str] = None

# Telemetry bridge
async def _forward_telemetry_async(event):
    try:
        details = json.loads(json.dumps(event.__dict__, default=json_serial))
        async with httpx.AsyncClient() as client:
            await client.post(
                f"{CONTROL_PLANE_URL}/api/telemetry/events",
                json={
                    "agent_id": getattr(event, "agent_name", SWARM_ID),
                    "session_id": getattr(event, "session_id", "unknown"),
                    "event_type": event.__class__.__name__,
                    "details": details
                },
                timeout=5.0
            )
    except Exception:
        pass

def forward_telemetry(event):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_forward_telemetry_async(event))
    except RuntimeError:
        asyncio.run(_forward_telemetry_async(event))

event_bus.subscribe(AgentStepStarted, forward_telemetry)
event_bus.subscribe(AgentStepCompleted, forward_telemetry)
event_bus.subscribe(TokenUsageReported, forward_telemetry)
from orkestra.events.base import ToolExecutionStarted, ToolExecutionCompleted
event_bus.subscribe(ToolExecutionStarted, forward_telemetry)
event_bus.subscribe(ToolExecutionCompleted, forward_telemetry)


async def build_agent_from_id(agent_id: str) -> Optional[Agent]:
    """Fetches agent config and builds an Agent instance."""
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CONTROL_PLANE_URL}/api/deployments/internal/config/{agent_id}",
                params={"token": DEPLOYMENT_TOKEN},
                timeout=10.0
            )
            if resp.status_code != 200:
                print(f"Failed to fetch config for {agent_id}: {resp.status_code} {resp.text}")
                return None
            config = resp.json()
    except Exception as e:
        print(f"Error fetching config for {agent_id}: {e}")
        return None

    llm_provider = config.get("llmProvider", "gemini").lower()
    llm_model = config.get("llm", "gemini-2.5-pro")
    api_key = config.get("api_key")
    
    if llm_provider == "openai":
        provider = OpenAIProvider(model=llm_model, api_key=api_key)
    elif llm_provider == "anthropic":
        provider = AnthropicProvider(model=llm_model, api_key=api_key)
    else:
        provider = GeminiProvider(model_name=llm_model, api_key=api_key)

    agent_tools = []
    # (Simplified tool parsing for MVP, in real implementation we'd reuse the logic from runner.py)
    # We will import the parsing logic from a common place if possible, but for now let's just do standard tools
    from orkestra.core.tools import HostTool, Tool as SandboxTool
    for t_data in config.get("tools", []):
        try:
            properties = {}
            required = []
            for p in t_data.get("parameters", []):
                properties[p["name"]] = {"type": p.get("type", "string"), "description": p.get("description", "")}
                if p.get("required"): required.append(p["name"])
            import re
            sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', t_data["name"])
            schema = {
                "type": "function",
                "function": {
                    "name": sanitized_name,
                    "description": t_data.get("description", ""),
                    "parameters": {"type": "object", "properties": properties, "required": required}
                }
            }
            namespace = {}
            exec(t_data["script"], namespace)
            func = namespace.get(t_data.get("entry_point", "execute"))
            if not func: continue
            func.__source_code__ = t_data["script"]
            tool_class = HostTool if t_data.get("tool_type") == "HOST" else SandboxTool
            agent_tools.append(tool_class(
                name=sanitized_name, description=t_data.get("description", ""), func=func, schema=schema,
                network_access=True, requires_approval=t_data.get("requires_approval", False)
            ))
        except Exception:
            pass

    from orkestra.memory.postgres import PostgresMemoryStore
    memory_store = PostgresMemoryStore(db_url=MEMORY_DATABASE_URL)

    from orkestra.core.context import TokenSummarizationStrategy
    
    compaction_tokens = config.get("compaction_tokens", 30000)
    max_iterations = config.get("max_iterations", 20)
    
    compaction_strategy = None
    if provider:
        compaction_strategy = TokenSummarizationStrategy(max_tokens=compaction_tokens, provider=provider, event_bus=event_bus)

    return Agent(
        id=agent_id,
        name=config.get("name", "Agent"),
        description=config.get("description", ""),
        system_prompt=config.get("system_prompt", ""),
        provider=provider,
        tools=agent_tools,
        memory=memory_store,
        workspace=workspace_store,
        tool_registry_url=TOOL_REGISTRY_URL,
        authorized_tool_ids=config.get("authorized_tool_ids", []) + config.get("authorized_mcp_ids", []),
        guardrails=[], # guardrails are currently not parsed in swarm_runner.py MVP
        event_bus=event_bus,
        max_iterations=max_iterations,
        compaction=compaction_strategy
    )

workspace_store = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    global swarm_executor_instance, workspace_store
    
    if not SWARM_ID or not DEPLOYMENT_TOKEN:
        print("Missing SWARM_ID or DEPLOYMENT_TOKEN.")
        sys.exit(1)
        
    print(f"Bootstrapping Swarm {SWARM_ID}")
    
    if WORKSPACE_DB_URL:
        try:
            from orkestra.workspace.postgres import PostgresWorkspaceStore
            workspace_store = PostgresWorkspaceStore(WORKSPACE_DB_URL, event_bus=event_bus)
            await workspace_store.initialize()
            print("Workspace store initialized.")
        except Exception as e:
            print(f"Failed to initialize workspace store: {e}")
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CONTROL_PLANE_URL}/api/deployments/internal/swarm_config/{SWARM_ID}",
                params={"token": DEPLOYMENT_TOKEN},
                timeout=10.0
            )
            resp.raise_for_status()
            swarm_config = resp.json()
    except Exception as e:
        print(f"Failed to fetch swarm config: {e}")
        sys.exit(1)

    leader_id = swarm_config["leader_agent_id"]
    subagents_info = swarm_config.get("subagents", [])
    
    leader_agent = await build_agent_from_id(leader_id)
    if not leader_agent:
        print("Failed to build leader agent.")
        sys.exit(1)
        
    swarm_executor_instance = SwarmExecutor(
        leader=leader_agent,
        subagent_factory=build_agent_from_id,
        event_bus=event_bus
    )
    # Pass full context to executor
    swarm_executor_instance.subagents_info = subagents_info
    
    yield
    print("Shutting down swarm.")

app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat(request: ChatRequest):
    global last_request_time, swarm_executor_instance
    last_request_time = time.time()
    
    # Isolate memory by creating a fresh UUID for the session!
    import uuid
    swarm_executor_instance.leader.session_id = request.session_id
    
    try:
        response_msg = await swarm_executor_instance.arun(
            user_input=request.message,
            subagents_info=swarm_executor_instance.subagents_info
        )
        
        return {
            "status": "success",
            "message": response_msg.content,
            "session_id": request.session_id,
            "agent": swarm_executor_instance.current_agent.name
        }
    except WorkflowPausedError as e:
        return {
            "status": "paused",
            "message": "Swarm paused for human-in-the-loop approval.",
            "details": e.details
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    global last_request_time, swarm_executor_instance, event_bus
    last_request_time = time.time()
    
    if not swarm_executor_instance:
        raise HTTPException(status_code=503, detail="Swarm Executor is not initialized")
        
    import asyncio
    import json
    from sse_starlette.sse import EventSourceResponse
    from orkestra.events.base import Event, WorkflowCompleted
    
    # Isolate memory by creating a fresh UUID for the session!
    swarm_executor_instance.leader.session_id = request.session_id
    
    queue = asyncio.Queue()
    
    def on_event(event):
        try:
            if getattr(event, "session_id", None) == request.session_id:
                loop = asyncio.get_running_loop()
                loop.create_task(queue.put(event))
        except RuntimeError:
            pass
            
    # Subscribe to all events
    event_bus.subscribe(Event, on_event)
    
    def json_serial(obj):
        import datetime
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()
        raise TypeError("Type %s not serializable" % type(obj))

    async def event_generator():
        # Start runner in background
        runner_task = asyncio.create_task(
            swarm_executor_instance.arun(
                user_input=request.message,
                subagents_info=swarm_executor_instance.subagents_info
            )
        )
        
        try:
            while True:
                fetch_event = asyncio.create_task(queue.get())
                done, pending = await asyncio.wait(
                    [fetch_event, runner_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                if fetch_event in done:
                    event = fetch_event.result()
                    event_data = {
                        "event_type": event.__class__.__name__,
                        "details": json.loads(json.dumps(event.__dict__, default=json_serial))
                    }
                    yield {"data": json.dumps(event_data)}
                    
                    if isinstance(event, WorkflowCompleted):
                        break
                
                if runner_task in done:
                    # Runner finished, drain queue
                    while not queue.empty():
                        event = queue.get_nowait()
                        event_data = {
                            "event_type": event.__class__.__name__,
                            "details": json.loads(json.dumps(event.__dict__, default=json_serial))
                        }
                        yield {"data": json.dumps(event_data)}
                    break
                    
            # Send final response
            try:
                result = await runner_task
                final_data = {
                    "event_type": "FinalResponse",
                    "details": {"content": result.message.content if hasattr(result, 'message') else str(result)}
                }
                yield {"data": json.dumps(final_data)}
            except WorkflowPausedError as e:
                paused_data = {
                    "event_type": "PausedForApproval",
                    "details": {
                        "tool_name": getattr(e, "tool_name", None),
                        "tool_call_id": getattr(e, "tool_call_id", None),
                        "tool_args": getattr(e, "tool_args", None)
                    }
                }
                yield {"data": json.dumps(paused_data)}
            except Exception as e:
                error_data = {
                    "event_type": "Error",
                    "details": {"content": f"Swarm Error: {str(e)}"}
                }
                yield {"data": json.dumps(error_data)}
            
        finally:
            event_bus._subscribers[Event].remove(on_event)
            
    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
