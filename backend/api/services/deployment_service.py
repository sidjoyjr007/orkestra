import uuid
import httpx
import json
import asyncio
from typing import AsyncGenerator
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status
from fastapi.responses import StreamingResponse

from backend.api.models.deployment import AgentDeployment
from backend.api.models.agent import AgentConfig
from backend.api.models.tool import Tool
from backend.api.models.guardrail import GuardrailConfig
from backend.api.models.llm import LlmConfig
from backend.api.models.mcp import McpConfig
from backend.api.models.hitl import HitlSession
from backend.api.core.crypto import decrypt_secret
from backend.api.core.deployment.provider import BaseDeploymentProvider

class DeploymentService:
    def __init__(self, db: AsyncSession, provider: BaseDeploymentProvider, control_plane_url: str):
        self.db = db
        self.provider = provider
        self.control_plane_url = control_plane_url

    async def deploy_agent(self, agent_id: str) -> dict:
        result = await self.db.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        agent = result.scalars().first()
        if not agent:
            raise ValueError("Agent not found")
            
        dep_result = await self.db.execute(select(AgentDeployment).where(AgentDeployment.agent_id == agent_id))
        deployment = dep_result.scalars().first()
        
        if not deployment:
            deployment = AgentDeployment(
                agent_id=agent_id,
                deployment_token=uuid.uuid4().hex
            )
            self.db.add(deployment)
        else:
            if deployment.status == "STOPPED" and deployment.container_id:
                try:
                    await self.provider.start(deployment.container_id)
                    deployment.status = "RUNNING"
                    await self.db.commit()
                    return {"message": "Agent resumed successfully", "status": "RUNNING", "port": deployment.port}
                except Exception:
                    try:
                        await self.provider.remove(deployment.container_id)
                    except Exception:
                        pass
            
            deployment.deployment_token = uuid.uuid4().hex
            if deployment.container_id:
                try:
                    await self.provider.remove(deployment.container_id)
                except Exception:
                    pass
                    
        deployment.status = "BUILDING"
        await self.db.commit()
        
        try:
            deploy_info = await self.provider.deploy(
                agent_id=agent_id,
                control_plane_url=self.control_plane_url,
                deployment_token=deployment.deployment_token
            )
            deployment.container_id = deploy_info["container_id"]
            deployment.port = deploy_info["port"]
            deployment.status = "RUNNING"
            await self.db.commit()
            return {"message": "Agent deployed successfully", "status": "RUNNING", "port": deployment.port}
        except Exception as e:
            deployment.status = "FAILED"
            await self.db.commit()
            raise e

    async def get_deployment_status(self, agent_id: str) -> dict:
        dep_result = await self.db.execute(select(AgentDeployment).where(AgentDeployment.agent_id == agent_id))
        deployment = dep_result.scalars().first()
        if not deployment:
            return {"status": "NOT_DEPLOYED"}
            
        if deployment.container_id:
            try:
                actual_status = await self.provider.get_status(deployment.container_id)
                if actual_status != deployment.status:
                    deployment.status = actual_status
                    await self.db.commit()
            except Exception:
                pass
                
        return {"status": deployment.status, "port": deployment.port}

    async def stop_deployment(self, agent_id: str) -> None:
        dep_result = await self.db.execute(select(AgentDeployment).where(AgentDeployment.agent_id == agent_id))
        deployment = dep_result.scalars().first()
        if not deployment:
            raise ValueError("Deployment not found")
            
        if deployment.container_id:
            try:
                await self.provider.stop(deployment.container_id)
            except Exception:
                pass
                
        deployment.status = "STOPPED"
        await self.db.commit()

    async def proxy_chat(self, agent_id: str, payload_dict: dict) -> dict:
        dep_result = await self.db.execute(select(AgentDeployment).where(AgentDeployment.agent_id == agent_id))
        deployment = dep_result.scalars().first()
        
        if not deployment or deployment.status != "RUNNING":
            raise ValueError("Agent is not currently running. Please deploy it first.")
            
        runner_url = f"http://localhost:{deployment.port}/chat"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(runner_url, json=payload_dict, timeout=60.0)
            response.raise_for_status()
            data = response.json()
            
            if data.get("status") == "PAUSED_FOR_APPROVAL":
                hitl = HitlSession(
                    agent_id=agent_id,
                    session_id=payload_dict["session_id"],
                    status="PENDING",
                    request_type="TOOL_APPROVAL",
                    context={
                        "tool_name": data.get("tool_name"),
                        "tool_call_id": data.get("tool_call_id"),
                        "tool_args": data.get("tool_args")
                    },
                    webhook_url=payload_dict.get("webhook_url")
                )
                self.db.add(hitl)
                await self.db.commit()
                data["hitl_id"] = str(hitl.id)
                
                # Dispatch webhook asynchronously if provided
                wurl = payload_dict.get("webhook_url")
                if wurl:
                    async def send_webhook():
                        async with httpx.AsyncClient() as wc:
                            try:
                                await wc.post(wurl, json={"event": "HITL_REQUIRED", "hitl_id": str(hitl.id), "details": hitl.context})
                            except Exception:
                                pass
                    asyncio.create_task(send_webhook())
                    
            return data

    async def proxy_chat_stream_generator(self, agent_id: str, payload_dict: dict) -> AsyncGenerator[bytes, None]:
        dep_result = await self.db.execute(select(AgentDeployment).where(AgentDeployment.agent_id == agent_id))
        deployment = dep_result.scalars().first()
        
        if not deployment or deployment.status != "RUNNING":
            yield f"data: {{\"event_type\": \"Error\", \"details\": {{\"content\": \"Agent is not currently running. Please deploy it first.\"}}}}\n\n".encode()
            return
            
        runner_url = f"http://localhost:{deployment.port}/chat/stream"
        
        async with httpx.AsyncClient(timeout=300.0) as client:
            try:
                async with client.stream("POST", runner_url, json=payload_dict) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_lines():
                        if not chunk:
                            continue
                        
                        if chunk.startswith("data: "):
                            data_str = chunk[6:]
                            try:
                                data = json.loads(data_str)
                                if data.get("event_type") == "PausedForApproval":
                                    details = data.get("details", {})
                                    hitl = HitlSession(
                                        agent_id=agent_id,
                                        session_id=payload_dict["session_id"],
                                        status="PENDING",
                                        request_type="TOOL_APPROVAL",
                                        context=details,
                                        webhook_url=payload_dict.get("webhook_url")
                                    )
                                    self.db.add(hitl)
                                    await self.db.commit()
                                    
                                    # Dispatch webhook asynchronously if provided
                                    wurl = payload_dict.get("webhook_url")
                                    if wurl:
                                        async def send_webhook_stream(hid, ctx, url):
                                            async with httpx.AsyncClient() as wc:
                                                try:
                                                    await wc.post(url, json={"event": "HITL_REQUIRED", "hitl_id": hid, "details": ctx})
                                                except Exception:
                                                    pass
                                        asyncio.create_task(send_webhook_stream(str(hitl.id), details, wurl))
                                        
                                    data["details"]["hitl_id"] = str(hitl.id)
                                    chunk = f"data: {json.dumps(data)}"
                            except Exception:
                                pass
                        
                        yield (chunk + "\n\n").encode()
            except httpx.RequestError as e:
                yield f"data: {{\"event_type\": \"Error\", \"details\": {{\"content\": \"Failed to communicate with agent runner: {str(e)}\"}}}}\n\n".encode()
            except httpx.HTTPStatusError as e:
                yield f"data: {{\"event_type\": \"Error\", \"details\": {{\"content\": \"Agent runner returned error: {e.response.text}\"}}}}\n\n".encode()

    async def get_internal_config(self, agent_id: str, token: str) -> dict:
        dep_result = await self.db.execute(select(AgentDeployment).where(AgentDeployment.agent_id == agent_id))
        deployment = dep_result.scalars().first()
        
        if not deployment or deployment.deployment_token != token:
            raise PermissionError("Invalid deployment token")
            
        agent_result = await self.db.execute(select(AgentConfig).where(AgentConfig.id == agent_id))
        agent = agent_result.scalars().first()
        if not agent:
            raise ValueError("Agent not found")
            
        # Fetch actual Tools
        tools_data = []
        if agent.selectedTools:
            for t_id in agent.selectedTools:
                t_res = await self.db.execute(select(Tool).where(Tool.id == t_id))
                t_obj = t_res.scalars().first()
                if t_obj:
                    tools_data.append({
                        "name": t_obj.name,
                        "description": t_obj.description,
                        "script": t_obj.script,
                        "parameters": t_obj.parameters,
                        "dependencies": t_obj.dependencies,
                        "entry_point": t_obj.entry_point,
                        "tool_type": t_obj.tool_type,
                        "requires_approval": t_obj.requires_approval
                    })
                    
        # Fetch actual Guardrails
        guardrails_data = []
        if agent.selectedGuardrails:
            for g_id in agent.selectedGuardrails:
                g_res = await self.db.execute(select(GuardrailConfig).where(GuardrailConfig.id == g_id))
                g_obj = g_res.scalars().first()
                if g_obj:
                    guardrails_data.append({
                        "name": g_obj.name,
                        "stage": g_obj.stage,
                        "action": g_obj.action,
                        "handlerType": g_obj.handlerType,
                        "rules": g_obj.rules
                    })
                    
        # Fetch API Key from LlmConfig
        api_key = None
        actual_model = agent.llm
        if agent.llmProvider and agent.llm:
            llm_result = await self.db.execute(
                select(LlmConfig).where(
                    LlmConfig.provider.ilike(agent.llmProvider),
                    LlmConfig.name == agent.llm
                )
            )
            llm_config = llm_result.scalars().first()
            if llm_config:
                api_key = llm_config.api_key
                actual_model = llm_config.model_name
                
        # Fetch MCP Servers
        mcps_data = []
        if getattr(agent, "selectedMcps", None):
            for m_id in agent.selectedMcps:
                m_res = await self.db.execute(select(McpConfig).where(McpConfig.id == m_id))
                m_obj = m_res.scalars().first()
                if m_obj:
                    headers = dict(m_obj.headers) if m_obj.headers else {}
                    secrets = m_obj.secrets or []
                    for s in secrets:
                        try:
                            headers[s["key"]] = decrypt_secret(s["value"])
                        except Exception as e:
                            print(f"Failed to decrypt MCP secret {s.get('key')}: {e}")
                    mcps_data.append({
                        "name": m_obj.name,
                        "endpoint": m_obj.endpoint,
                        "headers": headers
                    })
                    
        return {
            "name": agent.name,
            "description": agent.description,
            "system_prompt": agent.system_prompt,
            "llm": actual_model,
            "llmProvider": agent.llmProvider,
            "api_key": api_key,
            "tools": tools_data,
            "guardrails": guardrails_data,
            "mcps": mcps_data
        }
