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
