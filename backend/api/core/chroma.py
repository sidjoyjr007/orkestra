import json
import os
import chromadb
import uuid
import logging

logger = logging.getLogger(__name__)

# We use the ChromaDB HttpClient to match the runner's approach
# and assume ChromaDB is running as a container (e.g. host.docker.internal or localhost)
TOOL_REGISTRY_URL = os.environ.get("TOOL_REGISTRY_URL", "http://localhost:8100")

def get_chroma_collection(collection_name: str = "orkestra_tools"):
    from urllib.parse import urlparse
    parsed = urlparse(TOOL_REGISTRY_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8100
    
    try:
        client = chromadb.HttpClient(host=host, port=port)
        return client.get_or_create_collection(name=collection_name)
    except Exception as e:
        logger.warning(f"Failed to connect to ChromaDB at {TOOL_REGISTRY_URL}: {e}")
        return None

def embed_tool_in_vector_db(tool_id: str, name: str, description: str, schema_dict: dict, tool_type: str, mcp_url: str = None, mcp_id: str = None, code: str = None, network_access: bool = False):
    """
    Embeds a tool's semantic description into the vector DB for Tool RAG.
    Tools are embedded globally and filtered by authorized tool IDs during search.
    """
    collection = get_chroma_collection()
    if not collection:
        return
        
    # The text we want to embed is a semantic summary of the tool
    document = f"{name}: {description}"
    
    metadata = {
        "tool_id": str(tool_id),
        "type": tool_type,
        "schema": json.dumps(schema_dict),
        "network_access": network_access
    }
    
    if mcp_url:
        metadata["mcp_url"] = mcp_url
    if mcp_id:
        metadata["mcp_id"] = str(mcp_id)
    if code:
        metadata["code"] = code
        
    try:
        # Document ID is just the tool_id since they are global
        doc_id = str(tool_id)
        collection.upsert(
            documents=[document],
            metadatas=[metadata],
            ids=[doc_id]
        )
        logger.info(f"Successfully embedded tool {name} (ID: {tool_id}) globally")
    except Exception as e:
        logger.error(f"Failed to embed tool {tool_id} into ChromaDB: {e}")

def delete_tool_from_vector_db(tool_id: str = None, mcp_id: str = None):
    """
    Deletes a tool or all tools for an MCP from the vector database globally.
    """
    collection = get_chroma_collection()
    if not collection:
        return
        
    try:
        if tool_id:
            collection.delete(ids=[str(tool_id)])
        elif mcp_id:
            collection.delete(where={"mcp_id": str(mcp_id)})
    except Exception as e:
        logger.error(f"Failed to delete tools from ChromaDB: {e}")

def clear_agent_tools_from_vector_db(agent_id: str):
    """
    Deletes all tools associated with an agent from the vector database.
    """
    collection = get_chroma_collection()
    if not collection:
        return
        
    try:
        collection.delete(where={"agent_id": agent_id})
    except Exception as e:
        logger.error(f"Failed to clear tools for agent {agent_id} from ChromaDB: {e}")
