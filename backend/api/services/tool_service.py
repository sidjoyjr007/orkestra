import uuid
import ast
import tempfile
import os
import subprocess
import json
import platform
import sys
from typing import List, Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, cast, String, func
from backend.api.models.tool import Tool
from backend.api.core.crypto import encrypt_secret, decrypt_secret
from backend.api.core.chroma import embed_tool_in_vector_db, delete_tool_from_vector_db

class ToolService:
    def __init__(self, db: AsyncSession):
        self.db = db

    @staticmethod
    def extract_metadata(script: str) -> dict:
        deps = set()
        entry_point = "execute"
        try:
            tree = ast.parse(script)
            # Find first function definition to use as entry point
            for node in tree.body:
                if isinstance(node, ast.FunctionDef) or isinstance(node, ast.AsyncFunctionDef):
                    entry_point = node.name
                    break
                    
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        deps.add(alias.name.split('.')[0])
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        deps.add(node.module.split('.')[0])
        except SyntaxError:
            pass
        return {"deps": list(deps), "entry_point": entry_point}

    async def list_tools(
        self,
        user_id: str,
        role: str,
        limit: int = 50,
        offset: int = 0,
        q: Optional[str] = None
    ) -> dict:
        query = select(Tool)
        
        if role != "ADMIN":
            query = query.where(
                or_(
                    Tool.creator_id == user_id,
                    func.coalesce(Tool.is_public, False) == True,
                    func.coalesce(cast(Tool.allowed_roles, String), '[]').like(f'%"{role}"%')
                )
            )
            
        if q:
            query = query.where(Tool.name.ilike(f"%{q}%"))
            
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        tools = result.scalars().all()
        
        formatted_tools = []
        for t in tools:
            masked_env_vars = [{"key": ev["key"], "value": "*****"} for ev in (t.secrets or [])]
            formatted_tools.append({
                "id": str(t.id),
                "name": t.name,
                "desc": t.description,
                "params": t.parameters or [],
                "script": t.script,
                "envVars": masked_env_vars,
                "tool_type": t.tool_type,
                "is_public": t.is_public,
                "requires_approval": t.requires_approval,
                "network_access": t.network_access,
                "status": t.status,
                "dependencies": t.dependencies or [],
                "allowed_roles": t.allowed_roles or [],
                "creator_id": str(t.creator_id)
            })
            
        return {"items": formatted_tools, "total": len(formatted_tools)}

    async def save_tool(
        self,
        payload_dict: dict,
        user_id: str,
        user_role: str,
        user_permissions: List[str]
    ) -> str:
        tool_id = payload_dict.get("id") if payload_dict.get("id") else str(uuid.uuid4())
        
        import re
        sanitized_name = re.sub(r'[^a-zA-Z0-9_\.\-:]', '_', payload_dict["name"])
        if not re.match(r'^[a-zA-Z_]', sanitized_name):
            sanitized_name = '_' + sanitized_name
        payload_dict["name"] = sanitized_name[:128]
        
        result = await self.db.execute(select(Tool).where(Tool.id == tool_id))
        existing_tool = result.scalars().first()
        
        meta = self.extract_metadata(payload_dict["script"])
        deps = meta["deps"]
        entry_point = meta["entry_point"]
        
        # Handle Secrets encryption
        processed_secrets = []
        if existing_tool:
            existing_secrets_map = {ev["key"]: ev["value"] for ev in (existing_tool.secrets or [])}
        else:
            existing_secrets_map = {}
            
        for ev in payload_dict.get("envVars", []):
            key = ev["key"]
            val = ev["value"]
            if val == "*****":
                processed_secrets.append({
                    "key": key,
                    "value": existing_secrets_map.get(key, "")
                })
            else:
                encrypted_val = encrypt_secret(val)
                processed_secrets.append({
                    "key": key,
                    "value": encrypted_val
                })
        
        params_list = payload_dict.get("params", [])
        
        if existing_tool:
            if "*" not in user_permissions and "tools:edit" not in user_permissions:
                raise PermissionError("Missing required permission: tools:edit")
                
            if existing_tool.creator_id != user_id and user_role != "ADMIN":
                raise PermissionError("Not authorized to edit this tool")
                
            existing_tool.name = payload_dict["name"]
            existing_tool.description = payload_dict["desc"]
            existing_tool.parameters = params_list
            existing_tool.script = payload_dict["script"]
            existing_tool.secrets = processed_secrets
            existing_tool.tool_type = payload_dict.get("tool_type", "SANDBOX")
            existing_tool.is_public = payload_dict.get("is_public", False)
            existing_tool.requires_approval = payload_dict.get("requires_approval", False)
            existing_tool.network_access = payload_dict.get("network_access", False)
            existing_tool.status = payload_dict.get("status", "DRAFT")
            existing_tool.dependencies = deps
            existing_tool.entry_point = entry_point
            existing_tool.allowed_roles = payload_dict.get("allowed_roles") or []
        else:
            if "*" not in user_permissions and "tools:create" not in user_permissions:
                raise PermissionError("Missing required permission: tools:create")
                
            new_tool = Tool(
                id=tool_id,
                name=payload_dict["name"],
                description=payload_dict["desc"],
                parameters=params_list,
                script=payload_dict["script"],
                secrets=processed_secrets,
                tool_type=payload_dict.get("tool_type", "SANDBOX"),
                is_public=payload_dict.get("is_public", False),
                requires_approval=payload_dict.get("requires_approval", False),
                network_access=payload_dict.get("network_access", False),
                status=payload_dict.get("status", "DRAFT"),
                dependencies=deps,
                entry_point=entry_point,
                allowed_roles=payload_dict.get("allowed_roles") or [],
                creator_id=user_id
            )
            self.db.add(new_tool)
            
        await self.db.commit()
        
        # Build schema dict for embedding
        properties = {}
        required = []
        for p in params_list:
            properties[p["name"]] = {
                "type": p.get("type", "string"),
                "description": p.get("description", "")
            }
            if p.get("required"):
                required.append(p["name"])
                
        schema_dict = {
            "type": "function",
            "function": {
                "name": payload_dict["name"],
                "description": payload_dict["desc"],
                "parameters": {
                    "type": "object",
                    "properties": properties,
                    "required": required
                }
            }
        }
        
        # Embed tool globally
        embed_tool_in_vector_db(
            tool_id=str(tool_id),
            name=payload_dict["name"],
            description=payload_dict["desc"],
            schema_dict=schema_dict,
            tool_type=payload_dict.get("tool_type", "SANDBOX"),
            code=payload_dict["script"],
            network_access=payload_dict.get("network_access", False)
        )
        
        return str(tool_id)

    async def delete_tool(self, tool_id: str, user_id: str, user_role: str) -> None:
        result = await self.db.execute(select(Tool).where(Tool.id == tool_id))
        tool = result.scalars().first()
        
        if not tool:
            raise ValueError("Tool not found")
            
        if tool.creator_id != user_id and user_role != "ADMIN":
            raise PermissionError("Not authorized to delete this tool")
            
        await self.db.delete(tool)
        await self.db.commit()
        
        # Remove from vector db
        delete_tool_from_vector_db(tool_id=tool_id)

    async def execute_tool(
        self,
        tool_id: str,
        parameters: dict,
        user_id: str,
        user_role: str
    ) -> dict:
        result = await self.db.execute(select(Tool).where(Tool.id == tool_id))
        tool = result.scalars().first()
        
        if not tool:
            raise ValueError("Tool not found")
            
        if tool.creator_id != user_id and not tool.is_public and user_role != "ADMIN" and (not tool.allowed_roles or user_role not in tool.allowed_roles):
            raise PermissionError("Not authorized to execute this tool")
            
        script_content = tool.script
        
        # Inject Secrets
        if tool.secrets:
            for ev in tool.secrets:
                try:
                    decrypted = decrypt_secret(ev["value"])
                    script_content = script_content.replace(f"{{{{{ev['key']}}}}}", decrypted)
                except Exception:
                    pass
                    
        # Append runner block
        runner_block = f"""
import json
import sys
import asyncio

if __name__ == "__main__":
    try:
        params = json.loads(sys.argv[1])
        if asyncio.iscoroutinefunction({tool.entry_point}):
            result = asyncio.run({tool.entry_point}(**params))
        else:
            result = {tool.entry_point}(**params)
        print(result)
    except Exception as e:
        print(f"Execution Error: {{str(e)}}", file=sys.stderr)
        sys.exit(1)
"""
        script_content += "\n" + runner_block
        
        is_mac = platform.system() == "Darwin"
        
        with tempfile.TemporaryDirectory() as tmpdir:
            mount_dir = tmpdir
            if is_mac and tmpdir.startswith("/var"):
                mount_dir = "/private" + tmpdir
                
            script_path = os.path.join(tmpdir, "script.py")
            with open(script_path, "w") as f:
                f.write(script_content)
                
            deps = tool.dependencies or []
            if deps:
                deps = [d for d in deps if d not in sys.stdlib_module_names]
                
            req_path = os.path.join(tmpdir, "requirements.txt")
            with open(req_path, "w") as f:
                f.write("\n".join(deps))
                
            params_str = json.dumps(parameters)
            
            cmd = ["docker", "run", "--rm", "-v", f"{mount_dir}:/workspace", "-w", "/workspace", "python:3.11-slim"]
            
            if deps:
                sh_cmd = f"pip install -q -r requirements.txt && python script.py '{params_str}'"
                cmd.extend(["sh", "-c", sh_cmd])
            else:
                cmd.extend(["python", "script.py", params_str])
                
            try:
                process = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                return {
                    "stdout": process.stdout.strip(),
                    "stderr": process.stderr.strip(),
                    "exit_code": process.returncode
                }
            except subprocess.TimeoutExpired:
                return {
                    "stdout": "",
                    "stderr": "Execution timed out after 30 seconds.",
                    "exit_code": 124
                }
            except Exception as e:
                return {
                    "stdout": "",
                    "stderr": str(e),
                    "exit_code": 1
                }
