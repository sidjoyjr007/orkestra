from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, cast, String
from pydantic import BaseModel, ConfigDict
from typing import List, Optional, Any, Dict
import json

from backend.api.core.database import get_db
from backend.api.core.dependencies import get_current_user_token, require_permission
from backend.api.models.mcp import McpConfig
from backend.api.core.crypto import encrypt_secret, decrypt_secret
from backend.api.core.chroma import embed_tool_in_vector_db, delete_tool_from_vector_db
from mcp.client.sse import sse_client
from mcp.client.session import ClientSession
import asyncio

router = APIRouter()

async def _sync_mcp_tools(mcp: McpConfig):
    """Fetches all tools from the MCP server and embeds them globally in ChromaDB."""
    # Build final headers
    headers_dict = mcp.headers or {}
    final_headers = {}
    for k, v in headers_dict.items():
        val = str(v)
        for secret in (mcp.secrets or []):
            key_name = secret.get("key")
            encrypted_val = secret.get("value")
            if encrypted_val:
                try:
                    decrypted_val = decrypt_secret(encrypted_val)
                    val = val.replace(f"{{{{{key_name}}}}}", decrypted_val)
                except Exception:
                    pass
        final_headers[k] = val

    try:
        async with sse_client(mcp.endpoint, headers=final_headers) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                
                # Delete existing tools for this MCP before syncing
                delete_tool_from_vector_db(mcp_id=mcp.id)
                
                for t in tools_response.tools:
                    # Construct a unique tool_id for the MCP tool
                    tool_id = f"{mcp.id}_{t.name}"
                    
                    schema_dict = {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description or "No description provided.",
                            "parameters": t.inputSchema
                        }
                    }
                    
                    embed_tool_in_vector_db(
                        tool_id=tool_id,
                        name=t.name,
                        description=t.description or "",
                        schema_dict=schema_dict,
                        tool_type="mcp",
                        mcp_url=mcp.endpoint,
                        mcp_id=mcp.id
                    )
    except Exception as e:
        print(f"Error syncing MCP tools for {mcp.name}: {e}")

class McpSecret(BaseModel):
    key: str
    value: str

class McpCreateUpdate(BaseModel):
    id: Optional[str] = None
    name: str
    endpoint: str
    is_public: bool = False
    headers: str # We accept stringified JSON for headers
    envVars: List[McpSecret] = [] # The frontend sends this array
    allowed_roles: Optional[List[str]] = []

class McpResponse(BaseModel):
    id: str
    name: str
    endpoint: str
    is_public: bool
    headers: str
    envVars: List[Dict[str, Any]] # We return masked/empty values for secrets
    allowed_roles: List[str]
    creator_id: str

    model_config = ConfigDict(from_attributes=True)

@router.get("", response_model=List[McpResponse])
async def list_mcps(
    limit: int = 50,
    offset: int = 0,
    q: Optional[str] = None,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("mcps:read")),
    db: AsyncSession = Depends(get_db)
):
    query = select(McpConfig)
    
    user_id = user["sub"]
    role = user.get("role", "VIEWER")
    
    if role != "ADMIN":
        query = query.where(
            or_(
                McpConfig.is_public == True, 
                McpConfig.creator_id == user_id,
                cast(McpConfig.allowed_roles, String).like(f'%"{role}"%')
            )
        )
        
    if q:
        query = query.where(or_(McpConfig.name.ilike(f"%{q}%"), McpConfig.endpoint.ilike(f"%{q}%")))
        
    query = query.limit(limit).offset(offset)
    result = await db.execute(query)
    mcps = result.scalars().all()
    
    responses = []
    for m in mcps:
        # Return keys but not values
        safe_env_vars = [{"key": secret.get("key"), "value": ""} for secret in m.secrets] if m.secrets else []
        responses.append(McpResponse(
            id=m.id,
            name=m.name,
            endpoint=m.endpoint,
            is_public=m.is_public,
            headers=json.dumps(m.headers) if m.headers else "{\n}",
            envVars=safe_env_vars,
            allowed_roles=m.allowed_roles or [],
            creator_id=m.creator_id
        ))
    return responses

@router.post("", response_model=McpResponse)
async def create_mcp(
    payload: McpCreateUpdate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("mcps:create")),
    db: AsyncSession = Depends(get_db)
):
    try:
        headers_dict = json.loads(payload.headers) if payload.headers.strip() else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid headers JSON")

    # Encrypt secrets
    encrypted_secrets = []
    for secret in payload.envVars:
        if secret.value.strip():
            encrypted_secrets.append({
                "key": secret.key,
                "value": encrypt_secret(secret.value)
            })

    new_mcp = McpConfig(
        id=payload.id if payload.id else None,
        name=payload.name,
        endpoint=payload.endpoint,
        is_public=payload.is_public,
        headers=headers_dict,
        secrets=encrypted_secrets,
        allowed_roles=payload.allowed_roles or [],
        creator_id=user["sub"]
    )
    
    db.add(new_mcp)
    await db.commit()
    await db.refresh(new_mcp)
    
    # Sync tools asynchronously
    asyncio.create_task(_sync_mcp_tools(new_mcp))
    
    safe_env_vars = [{"key": secret.get("key"), "value": ""} for secret in new_mcp.secrets] if new_mcp.secrets else []
    
    return McpResponse(
        id=new_mcp.id,
        name=new_mcp.name,
        endpoint=new_mcp.endpoint,
        is_public=new_mcp.is_public,
        headers=json.dumps(new_mcp.headers) if new_mcp.headers else "{\n}",
        envVars=safe_env_vars,
        allowed_roles=new_mcp.allowed_roles or [],
    creator_id=new_mcp.creator_id
    )

@router.put("/{mcp_id}", response_model=McpResponse)
async def update_mcp(
    mcp_id: str,
    payload: McpCreateUpdate,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("mcps:edit")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(McpConfig).where(McpConfig.id == mcp_id))
    mcp = result.scalars().first()
    
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
        
    if user.get("role") != "ADMIN" and mcp.creator_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Not authorized to edit this MCP")

    try:
        headers_dict = json.loads(payload.headers) if payload.headers.strip() else {}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid headers JSON")

    # Map existing secrets
    existing_secrets = {s["key"]: s["value"] for s in (mcp.secrets or [])}
    
    encrypted_secrets = []
    for secret in payload.envVars:
        if secret.value.strip(): # Updated value
            encrypted_secrets.append({
                "key": secret.key,
                "value": encrypt_secret(secret.value)
            })
        else: # Keep old value
            if secret.key in existing_secrets:
                encrypted_secrets.append({
                    "key": secret.key,
                    "value": existing_secrets[secret.key]
                })

    mcp.name = payload.name
    mcp.endpoint = payload.endpoint
    mcp.is_public = payload.is_public
    mcp.headers = headers_dict
    mcp.secrets = encrypted_secrets
    
    if payload.allowed_roles is not None:
        if user.get("role") == "ADMIN" or mcp.creator_id == user["sub"]:
            mcp.allowed_roles = payload.allowed_roles
    
    
    await db.commit()
    await db.refresh(mcp)
    
    # Sync tools asynchronously
    asyncio.create_task(_sync_mcp_tools(mcp))
    
    safe_env_vars = [{"key": secret.get("key"), "value": ""} for secret in mcp.secrets] if mcp.secrets else []
    
    return McpResponse(
        id=mcp.id,
        name=mcp.name,
        endpoint=mcp.endpoint,
        is_public=mcp.is_public,
        headers=json.dumps(mcp.headers) if mcp.headers else "{\n}",
        envVars=safe_env_vars,
        creator_id=mcp.creator_id
    )

@router.delete("/{mcp_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_mcp(
    mcp_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("mcps:delete")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(McpConfig).where(McpConfig.id == mcp_id))
    mcp = result.scalars().first()
    
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
        
    if user.get("role") != "ADMIN" and mcp.creator_id != user["sub"]:
        raise HTTPException(status_code=403, detail="Not authorized to delete this MCP")

    await db.delete(mcp)
    await db.commit()
    
    # Remove tools from vector db
    delete_tool_from_vector_db(mcp_id=mcp_id)
    
    return None

class McpTestResponse(BaseModel):
    tools: List[Dict[str, Any]]

@router.get("/{mcp_id}/test", response_model=McpTestResponse)
async def test_mcp(
    mcp_id: str,
    user: dict = Depends(get_current_user_token),
    _: dict = Depends(require_permission("mcps:read")),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(McpConfig).where(McpConfig.id == mcp_id))
    mcp = result.scalars().first()
    
    if not mcp:
        raise HTTPException(status_code=404, detail="MCP not found")
        
    if user.get("role") != "ADMIN" and not mcp.is_public and mcp.creator_id != user["sub"]:
        if user.get("role") not in (mcp.allowed_roles or []):
            raise HTTPException(status_code=403, detail="Not authorized to access this MCP")

    # Map headers and replace secrets
    headers_dict = mcp.headers or {}
    final_headers = {}
    for k, v in headers_dict.items():
        val = str(v)
        for secret in (mcp.secrets or []):
            key_name = secret.get("key")
            encrypted_val = secret.get("value")
            if encrypted_val:
                try:
                    decrypted_val = decrypt_secret(encrypted_val)
                    val = val.replace(f"{{{{{key_name}}}}}", decrypted_val)
                except Exception:
                    pass
        final_headers[k] = val

    try:
        async with sse_client(mcp.endpoint, headers=final_headers) as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                tools_response = await session.list_tools()
                
                # Format tools response nicely
                serialized_tools = []
                for t in tools_response.tools:
                    serialized_tools.append({
                        "name": t.name,
                        "description": t.description or "No description provided.",
                        "schema": t.inputSchema
                    })
                
                return McpTestResponse(tools=serialized_tools)
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to connect to MCP server: {str(e)}")
