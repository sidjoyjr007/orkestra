import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import chromadb

from orkestra.core.tools import Tool
from orkestra.mcp.http_client import MCPTool
from orkestra.core.telemetry import get_logger
from orkestra.events.base import ToolSearchStarted, ToolSearchCompleted

logger = get_logger("orkestra.core.tool_registry")

class ToolRegistry:
    """
    Connects to an external ChromaDB Vector Database to perform Semantic Tool Routing (Tool RAG).
    Assumes tools are pre-embedded by an external process.
    """
    def __init__(self, url: str, agent_id: str, collection_name: str = "orkestra_tools", event_bus: Optional[Any] = None, authorized_tool_ids: Optional[List[str]] = None):
        self.url = url
        self.agent_id = agent_id
        self.event_bus = event_bus
        self.authorized_tool_ids = authorized_tool_ids or []
        
        parsed = urlparse(url)
        host = parsed.hostname or "localhost"
        port = parsed.port or 8000
        
        try:
            self.client = chromadb.HttpClient(host=host, port=port)
            self.collection = self.client.get_collection(name=collection_name)
        except Exception as e:
            logger.warning(f"Failed to connect to ChromaDB at {url}. Tool retrieval may fail: {e}")
            self.collection = None

    def search(self, query: str, top_k: int = 3, threshold: float = 0.4) -> List[Tool]:
        """
        Searches the vector database for tools relevant to the query.
        Filters by agent_id and applies a similarity threshold.
        """
        if self.event_bus:
            self.event_bus.publish(ToolSearchStarted(agent_id=self.agent_id, query=query))
            
        if not self.collection:
            logger.error("ChromaDB collection is not initialized.")
            if self.event_bus:
                self.event_bus.publish(ToolSearchCompleted(agent_id=self.agent_id, tools_found=0))
            return []
            
        try:
            # Note: ChromaDB distances are often cosine distance or L2.
            # Assuming default L2, lower distance is more similar.
            # A threshold mapping might be required depending on the embedding function.
            # If agent has no authorized tools, it cannot find any tools
            if not self.authorized_tool_ids:
                if self.event_bus:
                    self.event_bus.publish(ToolSearchCompleted(agent_id=self.agent_id, tools_found=0))
                return []

            # We use an $in or $or query to allow the agent to search for MCPs or specific tools
            # If a tool is an MCP tool, its tool_id is {mcp_id}_{tool_name}. But authorized_tool_ids contains the mcp_id.
            # So we check if the tool's mcp_id is in authorized_tool_ids, OR the tool's tool_id is in authorized_tool_ids.
            where_clause = {
                "$or": [
                    {"tool_id": {"$in": self.authorized_tool_ids}},
                    {"mcp_id": {"$in": self.authorized_tool_ids}}
                ]
            }

            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_clause
            )
            
            tools = []
            if not results['documents'] or not results['documents'][0]:
                if self.event_bus:
                    self.event_bus.publish(ToolSearchCompleted(agent_id=self.agent_id, tools_found=0))
                return tools
                
            for i in range(len(results['documents'][0])):
                distance = results['distances'][0][i]
                metadata = results['metadatas'][0][i]
                
                # Convert L2 distance to approximate cosine similarity percentage
                # For normalized vectors, Cosine_Sim = 1 - (L2^2 / 2)
                # However, ChromaDB default L2 distances for MiniLM can be up to ~2.0
                # A rough heuristic for percentage is:
                similarity = 1.0 - (distance / 2.0)
                
                if similarity < threshold:
                    continue
                    
                tool = self._reconstruct_tool(metadata)
                if tool:
                    tools.append(tool)
                    
            if self.event_bus:
                self.event_bus.publish(ToolSearchCompleted(agent_id=self.agent_id, tools_found=len(tools)))
            return tools
        except Exception as e:
            logger.error(f"Error querying ToolRegistry: {e}")
            if self.event_bus:
                self.event_bus.publish(ToolSearchCompleted(agent_id=self.agent_id, tools_found=0))
            return []
            
    def _reconstruct_tool(self, metadata: Dict[str, Any]) -> Optional[Tool]:
        """
        Reconstructs a Tool object from ChromaDB metadata.
        """
        try:
            schema_str = metadata.get("schema")
            if not schema_str:
                return None
                
            schema = json.loads(schema_str)
            name = schema.get("function", {}).get("name", "unknown")
            description = schema.get("function", {}).get("description", "")
            
            tool_type = metadata.get("type", "local")
            
            if tool_type == "mcp":
                # Reconstruct an MCPTool
                import httpx
                mcp_url = metadata.get("mcp_url")
                if not mcp_url:
                    logger.error(f"MCP tool '{name}' is missing mcp_url in metadata.")
                    return None
                    
                # We pass headers and url, MCPTool will dynamically create a session when executed.
                headers = {"Accept": "text/event-stream, application/json"}
                mcp_name = metadata.get("mcp_name", name)
                
                tool = MCPTool(
                    name=name,
                    mcp_name=mcp_name,
                    description=description,
                    schema=schema,
                    url=mcp_url,
                    headers=headers
                )
                return tool
            else:
                # Dynamic local tool reconstruction from source code in VectorDB
                code = metadata.get("code")
                if code:
                    # Create a safe, isolated namespace dictionary for compilation
                    namespace = {}
                    try:
                        # Dynamically compile and execute the code string into the namespace
                        exec(code, namespace)
                        func = namespace.get(name)
                        if not func or not callable(func):
                            # Try to find the function name using AST if the schema name doesn't match
                            import ast
                            tree = ast.parse(code)
                            func_defs = [n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
                            if func_defs:
                                # Usually the main function is the last one defined or the only one
                                func = namespace.get(func_defs[-1])
                                
                        if not func or not callable(func):
                            raise ValueError(f"Compiled code did not contain a callable function named '{name}' or any other identifiable function")
                            
                        # Attach the source code so Tool.run() can extract it without inspect.getsource
                        func.__source_code__ = code
                    except Exception as code_exc:
                        err_msg = str(code_exc)
                        logger.error(f"Failed to dynamically compile code for tool '{name}': {err_msg}")
                        def dummy_func(e=err_msg, **kwargs):
                            raise NotImplementedError(f"Local tool '{name}' failed to compile from DB: {e}")
                        func = dummy_func
                else:
                    def dummy_func(**kwargs):
                        raise NotImplementedError(f"Local tool '{name}' has no 'code' in metadata.")
                    func = dummy_func
                    
                dependencies_str = metadata.get("dependencies", "[]")
                try:
                    dependencies = json.loads(dependencies_str)
                except Exception:
                    dependencies = []
                network_access = bool(metadata.get("network_access", False))
                
                requires_approval = str(metadata.get("requires_approval", "false")).lower() == "true"
                if tool_type == "host_tool":
                    from orkestra.core.tools import HostTool
                    return HostTool(name=name, description=description, func=func, schema=schema, dependencies=dependencies, network_access=network_access, requires_approval=requires_approval)
                else:
                    return Tool(name=name, description=description, func=func, schema=schema, dependencies=dependencies, network_access=network_access, requires_approval=requires_approval)
                
        except Exception as e:
            logger.error(f"Failed to reconstruct tool from metadata: {e}")
            return None

    def inject_semantic_tools(self, agent) -> None:
        """
        Synchronous fallback for intent extraction (avoids workspace if async is required).
        """
        last_intent = None
        for msg in reversed(agent.messages):
            if msg.role == "user" or (msg.role == "assistant" and msg.content and "Plan:" in msg.content):
                last_intent = msg.content
                break
                
        # Always extract historical tool names to ensure they are loaded
        historical_tool_names = set()
        for msg in agent.messages:
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    historical_tool_names.add(tc.function_name)
                    
        for tool_name in historical_tool_names:
            found = self.search(tool_name, threshold=0.2)
            existing_names = {t.name for t in agent.tools}
            for t in found:
                if t.name not in existing_names:
                    agent.tools.append(t)
                    
        if last_intent:
            logger.info("Performing Semantic Tool Routing (Tool RAG) against VectorDB...", extra={"extra_data": {"agent_id": agent.id, "intent": last_intent[:50]}})
            found_tools = self.search(last_intent, threshold=0.25)
            existing_names = {t.name for t in agent.tools}
            for t in found_tools:
                if t.name not in existing_names:
                    agent.tools.append(t)
                    logger.info(f"Dynamically injected tool: {t.name}", extra={"extra_data": {"agent_id": agent.id, "tool_name": t.name}})

    async def ainject_semantic_tools(self, agent) -> None:
        """
        Extracts the semantic intent from the active plan (if any) or recent messages
        and injects relevant tools dynamically into the agent's toolbelt.
        """
        intent_query = None
        
        # 1. First, try to extract intent from an active plan
        if getattr(agent, "workspace", None):
            active_plan = await agent.workspace.aget_active_plan(agent.session_id)
            if active_plan:
                task_descriptions = [t.description for t in active_plan.tasks]
                intent_query = " ".join(task_descriptions) if task_descriptions else ""
        # 2. Fallback to last user message or assistant intent if no active plan
        if not intent_query:
            for msg in reversed(agent.messages):
                if msg.role == "user" or (msg.role == "assistant" and msg.content and "Plan:" in msg.content):
                    intent_query = msg.content
                    break
                    
        # 3. Always extract historical tool names to ensure they are loaded
        historical_tool_names = set()
        for msg in agent.messages:
            if msg.role == "assistant" and msg.tool_calls:
                for tc in msg.tool_calls:
                    historical_tool_names.add(tc.function_name)
                    
        for tool_name in historical_tool_names:
            found = self.search(tool_name, threshold=0.2)
            existing_names = {t.name for t in agent.tools}
            for t in found:
                if t.name not in existing_names:
                    agent.tools.append(t)
                    
        if intent_query:
            logger.info("Performing Semantic Tool Routing (Tool RAG) against VectorDB...", extra={"extra_data": {"agent_id": agent.id, "intent": intent_query[:50]}})
            found_tools = self.search(intent_query, threshold=0.25)
            existing_names = {t.name for t in agent.tools}
            for t in found_tools:
                if t.name not in existing_names:
                    agent.tools.append(t)
                    logger.info(f"Dynamically injected tool: {t.name}", extra={"extra_data": {"agent_id": agent.id, "tool_name": t.name}})
