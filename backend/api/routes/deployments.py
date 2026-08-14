import os
import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from typing import List, Optional
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token, require_permission
from backend.api.core.deployment.provider import LocalDockerProvider
from backend.api.services.deployment_service import DeploymentService

router = APIRouter()
docker_provider = LocalDockerProvider()

CONTROL_PLANE_URL = os.getenv("CONTROL_PLANE_URL", "http://host.docker.internal:8000")

class ChatRequest(BaseModel):
    message: Optional[str] = None
    session_id: str
    webhook_url: Optional[str] = None

from backend.api.models.chat import MessageModel
from sqlalchemy.future import select

def get_deployment_service(db: AsyncSession = Depends(get_db)) -> DeploymentService:
    return DeploymentService(db, docker_provider, CONTROL_PLANE_URL)

@router.post("/{agent_id}/deploy")
async def deploy_agent(
    agent_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("agents:edit")),
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        return await service.deploy_agent(agent_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Deployment failed: {str(e)}")

@router.post("/swarm/{swarm_id}/deploy")
async def deploy_swarm(
    swarm_id: str,
    user: dict = Depends(get_current_user_token),
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        return await service.deploy_swarm(swarm_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"Swarm deployment failed: {str(e)}")

@router.get("/swarm/{swarm_id}/status")
async def get_swarm_deployment_status(
    swarm_id: str,
    user: dict = Depends(get_current_user_token),
    service: DeploymentService = Depends(get_deployment_service)
):
    return await service.get_swarm_deployment(swarm_id)

@router.post("/swarm/{swarm_id}/stop")
async def stop_swarm_deployment(
    swarm_id: str,
    user: dict = Depends(get_current_user_token),
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        await service.stop_swarm(swarm_id)
        return {"message": "Swarm deployment stopped successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/{agent_id}/status")
async def get_deployment_status(
    agent_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("agents:read")),
    service: DeploymentService = Depends(get_deployment_service)
):
    return await service.get_deployment_status(agent_id)

@router.post("/{agent_id}/stop")
async def stop_deployment(
    agent_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("agents:edit")),
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        await service.stop_deployment(agent_id)
        return {"message": "Agent stopped successfully"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/{agent_id}/chat")
async def proxy_chat(
    agent_id: str,
    payload: ChatRequest,
    user: dict = Depends(get_current_user_token),
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        return await service.proxy_chat(agent_id, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Agent runner returned error: {e.response.text}")

@router.post("/{agent_id}/chat/stream")
async def proxy_chat_stream(
    agent_id: str,
    payload: ChatRequest,
    user: dict = Depends(get_current_user_token),
    service: DeploymentService = Depends(get_deployment_service)
):
    gen = service.proxy_chat_stream_generator(agent_id, payload.model_dump())
    return StreamingResponse(gen, media_type="text/event-stream")

# INTERNAL API: Bootstrapping for the runner
@router.get("/internal/config/{agent_id}")
async def get_internal_config(
    agent_id: str,
    token: str,
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        return await service.get_internal_config(agent_id, token)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.get("/{agent_id}/sessions/{session_id}/messages")
async def get_session_messages(
    agent_id: str,
    session_id: str,
    user: dict = Depends(get_current_user_token),
    db: AsyncSession = Depends(get_db)
):
    # Fetch messages for this session
    query = select(MessageModel).where(MessageModel.session_id == session_id).order_by(MessageModel.id.asc())
    result = await db.execute(query)
    models = result.scalars().all()
    
    # Filter out internal telemetry so the UI only sees clean user/assistant dialogue
    filtered_messages = []
    last_assistant_content = None
    
    for m in models:
        # Hide system prompts and raw tool outputs
        if m.role in ["system", "tool"]:
            continue
            
        # Hide auto-injected Workflow Context blobs that pollute user chat history
        if m.role == "user" and m.content and str(m.content).strip().startswith("Workflow Context:"):
            continue
            
        # Hide assistant messages that are purely silent tool-calls (no text response)
        if m.role == "assistant" and (not m.content or str(m.content).strip() == ""):
            continue
            
        # Deduplicate consecutive identical assistant outputs (caused by tool-use loops)
        if m.role == "assistant":
            current_content = str(m.content).strip()
            if current_content == last_assistant_content:
                continue
            last_assistant_content = current_content
        else:
            last_assistant_content = None
            
        filtered_messages.append({
            "id": m.id,
            "role": m.role,
            "content": m.content,
            "name": m.name,
            "created_at": m.created_at.isoformat() if m.created_at else None
        })
        
    return filtered_messages

@router.get("/internal/swarm_config/{swarm_id}")
async def get_internal_swarm_config(
    swarm_id: str,
    token: str,
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        return await service.get_internal_swarm_config(swarm_id, token)
    except PermissionError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

@router.post("/swarm/{swarm_id}/chat")
async def proxy_swarm_chat(
    swarm_id: str,
    payload: ChatRequest,
    user: dict = Depends(get_current_user_token),
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        return await service.proxy_swarm_chat(swarm_id, payload.model_dump())
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=e.response.status_code, detail=f"Swarm runner returned error: {e.response.text}")

@router.post("/swarm/{swarm_id}/chat/stream")
async def proxy_swarm_chat_stream(
    swarm_id: str,
    payload: ChatRequest,
    user: dict = Depends(get_current_user_token),
    service: DeploymentService = Depends(get_deployment_service)
):
    try:
        return StreamingResponse(
            service.proxy_swarm_chat_stream(swarm_id, payload.model_dump()),
            media_type="text/event-stream"
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
