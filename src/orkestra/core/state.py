from typing import List, Dict, Any
from orkestra.core.tools import Tool

class AgentStateSerializer:
    """
    Handles the serialization and deserialization of an Agent's state.
    Responsible for checkpointing and reconstructing live network clients for MCP tools.
    """
    
    @staticmethod
    def to_dict(agent) -> dict:
        """Serializes the agent's core state and tools for checkpointing."""
        serialized_tools = []
        for tool in agent.tools:
            if hasattr(tool, '_mcp_tool_name'):
                # It's an MCP Tool
                serialized_tools.append({
                    "name": tool.name,
                    "type": "mcp",
                    "mcp_url": tool._url,
                    "mcp_name": tool._mcp_tool_name,
                    "schema": tool.schema,
                    "headers": getattr(tool, '_headers', {})
                })
            else:
                # Native Tool
                serialized_tools.append({
                    "name": tool.name,
                    "type": "native"
                })
                
        state = {
            "id": agent.id,
            "name": agent.name,
            "session_id": agent.session_id,
            "tools": serialized_tools
        }
        return state

    @staticmethod
    def load_state(agent, state: dict, base_tools: List[Tool]):
        """
        Deserializes a checkpoint state into the agent.
        Takes base_tools (the raw native python tools) to reconstruct references.
        """
        import httpx
        from orkestra.mcp.http_client import MCPTool
        
        if not state:
            return
            
        agent.id = state.get("id", agent.id)
        agent.name = state.get("name", agent.name)
        
        # Reconstruct agent.tools
        new_tools = []
        
        def _fix_schema(s: dict):
            import copy
            if not isinstance(s, dict): return s
            s = copy.deepcopy(s)
            def traverse(obj):
                if isinstance(obj, dict):
                    type_val = obj.get("type")
                    is_array = (type_val == "array") or (isinstance(type_val, list) and "array" in type_val)
                    is_object = (type_val == "object") or (isinstance(type_val, list) and "object" in type_val)
                    
                    if is_array:
                        if "items" not in obj or not isinstance(obj["items"], dict):
                            obj["items"] = {"type": "string"}
                        elif "type" not in obj["items"] and "anyOf" not in obj["items"]:
                            obj["items"]["type"] = "string"
                            
                    if is_object and "properties" not in obj:
                        obj["properties"] = {}
                        
                    for k, v in obj.items():
                        traverse(v)
                elif isinstance(obj, list):
                    for item in obj:
                        traverse(item)
            traverse(s)
            return s
            
        for tool_state in state.get("tools", []):
            if tool_state.get("type") == "native":
                # Find the matching native tool from base_tools
                matching_tool = next((t for t in base_tools if t.name == tool_state["name"]), None)
                if matching_tool:
                    new_tools.append(matching_tool)
            elif tool_state.get("type") == "mcp":
                # Reconstruct live MCP Tool
                fixed_schema = _fix_schema(tool_state["schema"])
                mcp_name = tool_state.get("mcp_name", tool_state["name"])
                new_tools.append(MCPTool(
                    name=tool_state["name"],
                    mcp_name=mcp_name,
                    description=fixed_schema.get("function", {}).get("description", ""),
                    schema=fixed_schema,
                    url=tool_state["mcp_url"],
                    headers=tool_state.get("headers", {}),
                    client=httpx.AsyncClient(timeout=30.0)
                ))
        agent.tools = new_tools
