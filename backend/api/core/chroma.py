import json
import os
import chromadb
import uuid
import logging

logger = logging.getLogger(__name__)

# We use the ChromaDB HttpClient to match the runner's approach
# and assume ChromaDB is running as a container (e.g. host.docker.internal or localhost)
CHROMA_URL = os.environ.get("CHROMA_URL", "http://localhost:8000")

def get_chroma_collection(collection_name: str = "orkestra_tools"):
    from urllib.parse import urlparse
    parsed = urlparse(CHROMA_URL)
    host = parsed.hostname or "localhost"
    port = parsed.port or 8000
    
    try:
        client = chromadb.HttpClient(host=host, port=port)
        return client.get_or_create_collection(name=collection_name)
    except Exception as e:
        logger.warning(f"Failed to connect to ChromaDB at {CHROMA_URL}: {e}")
        return None

def embed_tool_in_vector_db(agent_id: str, tool_id: str, name: str, description: str, schema_dict: dict, tool_type: str, mcp_url: str = None, code: str = None):
    """
    Embeds a tool's semantic description into the vector DB for Tool RAG.
    `agent_id` is required because tools are searched scoped to an agent.
    """
    collection = get_chroma_collection()
    if not collection:
        return
        
    # The text we want to embed is a semantic summary of the tool
    document = f"{name}: {description}"
    
    metadata = {
        "agent_id": agent_id,
        "tool_id": str(tool_id),
        "type": tool_type,
        "schema": json.dumps(schema_dict)
    }
    
    if mcp_url:
        metadata["mcp_url"] = mcp_url
    if code:
        metadata["code"] = code
        
    try:
        # Document ID must be unique per agent-tool combination
        doc_id = f"{agent_id}_{tool_id}"
        collection.upsert(
            documents=[document],
            metadatas=[metadata],
            ids=[doc_id]
        )
        logger.info(f"Successfully embedded tool {name} (ID: {tool_id}) for agent {agent_id}")
    except Exception as e:
        logger.error(f"Failed to embed tool {tool_id} into ChromaDB: {e}")

def delete_tool_from_vector_db(agent_id: str, tool_id: str):
    """
    Deletes a tool from the vector database.
    """
    collection = get_chroma_collection()
    if not collection:
        return
        
    try:
        doc_id = f"{agent_id}_{tool_id}"
        collection.delete(ids=[doc_id])
    except Exception as e:
        logger.error(f"Failed to delete tool {tool_id} from ChromaDB: {e}")

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
