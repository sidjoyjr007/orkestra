import json
import logging
from typing import List, Dict, Any, Optional
from urllib.parse import urlparse
import chromadb

from orkestra.core.tools import Tool
from orkestra.mcp.http_client import MCPTool
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.core.tool_registry")

class ToolRegistry:
    """
    Connects to an external ChromaDB Vector Database to perform Semantic Tool Routing (Tool RAG).
    Assumes tools are pre-embedded by an external process.
    """
    def __init__(self, url: str, agent_id: str, collection_name: str = "orkestra_tools"):
        self.url = url
        self.agent_id = agent_id
        
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
        if not self.collection:
            logger.error("ChromaDB collection is not initialized.")
            return []
            
        try:
            # Note: ChromaDB distances are often cosine distance or L2.
            # Assuming default L2, lower distance is more similar.
            # A threshold mapping might be required depending on the embedding function.
            results = self.collection.query(
                query_texts=[query],
                n_results=top_k,
                where={"agent_id": self.agent_id}
            )
            
            tools = []
            if not results['documents'] or not results['documents'][0]:
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
                    
            return tools
        except Exception as e:
            logger.error(f"Error querying ToolRegistry: {e}")
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
                    
                # We create a dummy client here. In a real system, the AgentRunner should 
                # manage this client, but for dynamic RAG reconstruction we instantiate it per tool.
                headers = {"Accept": "text/event-stream, application/json"}
                client = httpx.AsyncClient(timeout=30.0)
                
                tool = MCPTool(
                    name=name,
                    description=description,
                    schema=schema,
                    url=mcp_url,
                    headers=headers,
                    client=client
                )
                return tool
            else:
                # Local function tool reconstruction is extremely complex if the code isn't available.
                # For this architecture, we assume local tools can be looked up by name if needed,
                # or we just create a dummy tool that raises NotImplementedError.
                def dummy_func(**kwargs):
                    raise NotImplementedError("Dynamic local tool execution from VectorDB is not fully implemented.")
                    
                return Tool(name=name, description=description, func=dummy_func, schema=schema)
                
        except Exception as e:
            logger.error(f"Failed to reconstruct tool from metadata: {e}")
            return None

    def inject_semantic_tools(self, agent) -> None:
        """
        Extracts the semantic intent from the agent's recent messages and injects 
        relevant tools dynamically into the agent's toolbelt.
        """
        last_intent = None
        for msg in reversed(agent.messages):
            if msg.role == "user" or (msg.role == "assistant" and msg.content and "Plan:" in msg.content):
                last_intent = msg.content
                break
                
        if last_intent:
            logger.info("Performing Semantic Tool Routing (Tool RAG) against VectorDB...", extra={"extra_data": {"agent_id": agent.id, "intent": last_intent[:50]}})
            found_tools = self.search(last_intent)
            existing_names = {t.name for t in agent.tools}
            for t in found_tools:
                if t.name not in existing_names:
                    agent.tools.append(t)
                    logger.info(f"Dynamically injected tool: {t.name}", extra={"extra_data": {"agent_id": agent.id, "tool_name": t.name}})
