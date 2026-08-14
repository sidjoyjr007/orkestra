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
from typing import Dict, Any, Optional

def json_serial(obj):
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    raise TypeError(f"Type {type(obj)} not serializable")

# We assume orkestra package is installed in this container
from orkestra.core.agent import Agent
from orkestra.core.messages import Message
from orkestra.core.exceptions import WorkflowPausedError
from orkestra.providers.gemini_provider import GeminiProvider
from orkestra.providers.openai_provider import OpenAIProvider
from orkestra.providers.anthropic_provider import AnthropicProvider
from orkestra.events.bus import EventBus
from orkestra.events.base import Event, AgentStepStarted, AgentStepCompleted, TokenUsageReported
import asyncio

AGENT_ID = os.getenv("AGENT_ID")
CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://host.docker.internal:8000")
DEPLOYMENT_TOKEN = os.getenv("DEPLOYMENT_TOKEN")
MEMORY_DATABASE_URL = os.getenv("MEMORY_DATABASE_URL", "sqlite:///memory.db")
TOOL_REGISTRY_URL = os.getenv("TOOL_REGISTRY_URL")
WORKSPACE_DB_URL = os.getenv("WORKSPACE_DB_URL")

agent_instance = None
event_bus = EventBus()
last_request_time = time.time()
IDLE_TIMEOUT_SECONDS = int(os.getenv("IDLE_TIMEOUT_SECONDS", "600"))

class ChatRequest(BaseModel):
    message: Optional[str] = None
    session_id: str
    webhook_url: Optional[str] = None

async def telemetry_subscriber(event: Event):
    # Forward all Orkestra events back to Control Plane
    payload = {
        "agent_id": AGENT_ID,
        "session_id": getattr(event, "session_id", "unknown"),
        "event_type": event.__class__.__name__,
        "details": getattr(event, "__dict__", {})
    }
    
    # Fire and forget telemetry
    async def post_telemetry():
        try:
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{CONTROL_PLANE_URL}/api/telemetry/events", 
                    json=payload,
                    timeout=5.0
                )
        except Exception as e:
            print(f"Failed to post telemetry: {e}")
            
    asyncio.create_task(post_telemetry())

async def monitor_idle():
    """Background garbage collector for truncated tool artifacts."""
    while True:
        await asyncio.sleep(60) # Run every 60 seconds
        
        artifact_base = "/tmp/orkestra_artifacts"
        if not os.path.exists(artifact_base):
            continue
            
        current_time = time.time()
        ttl_seconds = 5400 # 90 minutes
        
        try:
            for session_dir in os.listdir(artifact_base):
                session_path = os.path.join(artifact_base, session_dir)
                if not os.path.isdir(session_path):
                    continue
                    
                # Check files in session directory
                files = os.listdir(session_path)
                for file_name in files:
                    file_path = os.path.join(session_path, file_name)
                    if os.path.isfile(file_path):
                        mtime = os.path.getmtime(file_path)
                        if current_time - mtime > ttl_seconds:
                            try:
                                os.remove(file_path)
                            except OSError:
                                pass
                
                # Check if directory is empty after deletions
                try:
                    if not os.listdir(session_path):
                        os.rmdir(session_path)
                except OSError:
                    pass
        except Exception as e:
            print(f"Error in artifact garbage collector: {e}")

@asynccontextmanager
async def lifespan(app: FastAPI):
    global agent_instance, init_error
    
    if not AGENT_ID or not DEPLOYMENT_TOKEN:
        print("Missing AGENT_ID or DEPLOYMENT_TOKEN. Exiting.")
        sys.exit(1)
        
    print(f"Bootstrapping Agent {AGENT_ID} from {CONTROL_PLANE_URL}")
    
    # Fetch Config
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"{CONTROL_PLANE_URL}/api/deployments/internal/config/{AGENT_ID}",
                params={"token": DEPLOYMENT_TOKEN},
                timeout=10.0
            )
            resp.raise_for_status()
            config = resp.json()
    except Exception as e:
        print(f"Failed to bootstrap configuration: {e}")
        sys.exit(1)
        
    # Subscribe all events to the telemetry bridge
    async def _forward_telemetry_async(event):
        try:
            import json
            from datetime import datetime
            
            def json_serial(obj):
                if isinstance(obj, datetime):
                    return obj.isoformat()
                raise TypeError(f"Type {type(obj)} not serializable")
                
            details = json.loads(json.dumps(event.__dict__, default=json_serial))
            
            async with httpx.AsyncClient() as client:
                await client.post(
                    f"{CONTROL_PLANE_URL}/api/telemetry/events",
                    json={
                        "agent_id": AGENT_ID,
                        "session_id": getattr(event, "session_id", "unknown"),
                        "event_type": event.__class__.__name__,
                        "details": details
                    },
                    timeout=5.0
                )
        except Exception as e:
            print(f"Telemetry forwarding failed: {e}")

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
    
    # Initialize actual Tool objects and Guardrails based on `config`
    # For MVP, we will initialize a generic Agent
    
    llm_provider = config.get("llmProvider", "gemini").lower()
    llm_model = config.get("llm", "gemini-2.5-pro")
    api_key = config.get("api_key")
    
    init_error = None
    try:
        if llm_provider == "openai":
            provider = OpenAIProvider(model=llm_model, api_key=api_key)
        elif llm_provider == "anthropic":
            provider = AnthropicProvider(model=llm_model, api_key=api_key)
        else:
            provider = GeminiProvider(model_name=llm_model, api_key=api_key)
    except Exception as e:
        print(f"Failed to initialize provider: {e}")
        provider = None
        init_error = str(e)
        
    # Parse tools dynamically
    from orkestra.core.tools import HostTool, Tool as SandboxTool
    from orkestra.memory.postgres import PostgresMemoryStore
    from orkestra.guardrails.base import GuardrailStage, GuardrailAction
    from orkestra.guardrails.regex import RegexGuardrail
    from orkestra.guardrails.llm_judge import LLMJudgeGuardrail
    
    agent_tools = []
    for t_data in config.get("tools", []):
        try:
            # Build OpenAI schema
            properties = {}
            required = []
            for p in t_data.get("parameters", []):
                properties[p["name"]] = {
                    "type": p.get("type", "string"),
                    "description": p.get("description", "")
                }
                if p.get("required"):
                    required.append(p["name"])
                    
            # Sanitize tool name for LLM schema (no spaces allowed)
            import re
            sanitized_name = re.sub(r'[^a-zA-Z0-9_-]', '_', t_data["name"])
            
            schema = {
                "type": "function",
                "function": {
                    "name": sanitized_name,
                    "description": t_data.get("description", ""),
                    "parameters": {
                        "type": "object",
                        "properties": properties,
                        "required": required
                    }
                }
            }
            
            # Extract callable function
            namespace = {}
            exec(t_data["script"], namespace)
            func = namespace.get(t_data.get("entry_point", "execute"))
            if not func:
                print(f"Warning: Tool {t_data['name']} missing entry point {t_data.get('entry_point')}")
                continue
                
            # Attach source code for the Sandbox extractor
            func.__source_code__ = t_data["script"]
            
            tool_class = HostTool if t_data.get("tool_type") == "HOST" else SandboxTool
                
            tool_kwargs = {
                "name": sanitized_name,
                "description": t_data.get("description", ""),
                "func": func,
                "schema": schema,
                "dependencies": t_data.get("dependencies", []),
                "network_access": True,
                "requires_approval": t_data.get("requires_approval", False)
            }
            
            agent_tools.append(tool_class(**tool_kwargs))
        except Exception as e:
            print(f"Failed to load tool {t_data.get('name')}: {e}")
            
    mcp_toolkits = []
    from orkestra.mcp.http_client import MCPHttpToolkit
    for m_data in config.get("mcps", []):
        try:
            print(f"Loading MCP Server: {m_data['name']}")
            endpoint = m_data["endpoint"]
            
            # Automatically rewrite localhost to host.docker.internal since runner is in a container
            endpoint = endpoint.replace("://localhost", "://host.docker.internal")
            endpoint = endpoint.replace("://127.0.0.1", "://host.docker.internal")
            
            toolkit = MCPHttpToolkit(url=endpoint, headers=m_data.get("headers", {}))
            mcp_tools = await toolkit.load_tools()
            agent_tools.extend(mcp_tools)
            mcp_toolkits.append(toolkit)
            print(f"Loaded {len(mcp_tools)} tools from MCP {m_data['name']}")
        except Exception as e:
            print(f"Failed to load MCP Server {m_data.get('name')}: {e}")
            
    agent_guardrails = []
    for g_data in config.get("guardrails", []):
        try:
            stage_str = g_data.get("stage", "input").upper()
            action_str = g_data.get("action", "block").upper()
            handler_type = g_data.get("handlerType", "regex").lower()
            rules = g_data.get("rules", "")
            
            # Map older values if any mismatch
            if handler_type == "llm_judge":
                handler_type = "llm-as-judge"
                
            stage = GuardrailStage(stage_str)
            action = GuardrailAction(action_str)
            
            if handler_type == "regex":
                agent_guardrails.append(RegexGuardrail(
                    stage=stage,
                    action_on_fail=action,
                    pattern=rules,
                    error_message=f"Content blocked by Regex Guardrail: {g_data.get('name')}"
                ))
            elif handler_type == "llm-as-judge":
                agent_guardrails.append(LLMJudgeGuardrail(
                    stage=stage,
                    action_on_fail=action,
                    prompt=rules,
                    provider=provider
                ))
        except Exception as e:
            print(f"Failed to load guardrail {g_data.get('name')}: {e}")
            
    memory_store = None
    try:
        db_url = os.environ.get("MEMORY_DATABASE_URL", "postgresql://orkestra:orkestra@host.docker.internal:5432/orkestra")
        memory_store = PostgresMemoryStore(db_url, event_bus=event_bus)
    except Exception as e:
        print(f"Warning: failed to initialize memory store: {e}")
        
    workspace_store = None
    if WORKSPACE_DB_URL:
        from orkestra.workspace.postgres import PostgresWorkspaceStore
        workspace_store = PostgresWorkspaceStore(WORKSPACE_DB_URL, event_bus=event_bus)
        await workspace_store.initialize()



    from orkestra.core.context import TokenSummarizationStrategy
    
    compaction_tokens = config.get("compaction_tokens", 30000)
    max_iterations = config.get("max_iterations", 20)
    
    compaction_strategy = None
    if provider:
        compaction_strategy = TokenSummarizationStrategy(max_tokens=compaction_tokens, provider=provider, event_bus=event_bus)

    agent_instance = Agent(
        name=config.get("name", "Deployed Agent"),
        description=config.get("description", "A deployed agent."),
        system_prompt=config.get("system_prompt", "You are a helpful assistant."),
        provider=provider, # might be None if failed
        tools=agent_tools,
        memory=memory_store,
        workspace=workspace_store,
        tool_registry_url=TOOL_REGISTRY_URL,
        authorized_tool_ids=config.get("authorized_tool_ids", []) + config.get("authorized_mcp_ids", []),
        guardrails=agent_guardrails,
        event_bus=event_bus,
        id=AGENT_ID,
        max_iterations=max_iterations,
        compaction=compaction_strategy
    )
    
    if init_error:
        agent_instance._init_error = init_error
        
    print(f"DEBUG: agent_instance tools count: {len(agent_instance.tools)}")
    
    # Start idle monitor
    asyncio.create_task(monitor_idle())
    
    yield
    print("Shutting down")
    for toolkit in mcp_toolkits:
        await toolkit.close()

app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat(req: ChatRequest):
    global last_request_time
    last_request_time = time.time()
    
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent is not initialized")
        
    if getattr(agent_instance, "_init_error", None):
        return {"response": f"🚨 **Agent Initialization Failed**\n\nThe agent container started, but failed to initialize its LLM provider. This is usually caused by missing API keys (e.g., `GEMINI_API_KEY`, `OPENAI_API_KEY`).\n\n**Error:** `{agent_instance._init_error}`"}
        
    # Clone agent for request isolation and auto-load memory
    request_agent = agent_instance.clone(session_id=req.session_id)

    # Run the agent step loop
    try:
        # 1. Add user message to history
        if req.message:
            await request_agent.aadd_message(Message(role="user", content=req.message))
        
        # 2. Use Orkestra's built-in AgentRunner
        from orkestra.workflows.runner import AgentRunner
        
        workflow_runner = AgentRunner(agent=request_agent, event_bus=event_bus)
        result = await workflow_runner.arun()
        
        return {"response": result.message.content}
    except WorkflowPausedError as e:
        return {
            "status": "PAUSED_FOR_APPROVAL",
            "tool_name": getattr(e, "tool_name", None),
            "tool_call_id": getattr(e, "tool_call_id", None),
            "tool_args": getattr(e, "tool_args", None)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/chat/stream")
async def chat_stream(req: ChatRequest):
    global last_request_time
    last_request_time = time.time()
    
    if not agent_instance:
        raise HTTPException(status_code=503, detail="Agent is not initialized")
        
    import json
    
    if getattr(agent_instance, "_init_error", None):
        from sse_starlette.sse import EventSourceResponse
        async def err_gen():
            yield {"data": json.dumps({
                "event_type": "Error",
                "details": {"content": f"🚨 **Agent Initialization Failed**\n\n**Error:** `{agent_instance._init_error}`"}
            })}
        return EventSourceResponse(err_gen())
        
    import asyncio
    from sse_starlette.sse import EventSourceResponse
    from orkestra.events.base import Event, WorkflowCompleted, ToolExecutionStarted, ToolExecutionCompleted
    from orkestra.workflows.runner import AgentRunner
    
    queue = asyncio.Queue()
    
    def on_event(event):
        try:
            if getattr(event, "session_id", None) == req.session_id:
                loop = asyncio.get_running_loop()
                loop.create_task(queue.put(event))
        except RuntimeError:
            pass
            
    # Subscribe to all events
    event_bus.subscribe(Event, on_event)
    
    request_agent = agent_instance.clone(session_id=req.session_id)
    print(f"DEBUG: request_agent tools count: {len(request_agent.tools)}")

    async def event_generator():
        # Add user message
        if req.message:
            await request_agent.aadd_message(Message(role="user", content=req.message))
        
        # Start runner in background
        workflow_runner = AgentRunner(agent=request_agent, event_bus=event_bus)
        runner_task = asyncio.create_task(workflow_runner.arun())
        
        try:
            while True:
                # Wait for next event or runner completion
                fetch_event = asyncio.create_task(queue.get())
                done, pending = await asyncio.wait(
                    [fetch_event, runner_task],
                    return_when=asyncio.FIRST_COMPLETED
                )
                
                if fetch_event in done:
                    event = fetch_event.result()
                    # Yield event to SSE
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
                    "details": {"content": result.message.content}
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
                    "details": {"content": f"Agent Error: {str(e)}"}
                }
                yield {"data": json.dumps(error_data)}
            
        finally:
            # Cleanup
            event_bus._subscribers[Event].remove(on_event)
            
    return EventSourceResponse(event_generator())

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
