import os
from orkestra.core.tools import Tool

def read_file_chunk_func(file_path: str, start_char: int, end_char: int, session_id: str) -> str:
    """Read a specific chunk of a file. Only allowed within the session's artifact directory."""
    allowed_dir = os.path.abspath(f"/tmp/orkestra_artifacts/{session_id}")
    target_path = os.path.abspath(file_path)
    
    # Sandboxing check
    if not target_path.startswith(allowed_dir):
        return f"Error: Permission denied. Can only read files inside {allowed_dir}"
        
    if not os.path.exists(target_path):
        return f"Error: File not found at {target_path}"
        
    try:
        with open(target_path, "r", encoding="utf-8") as f:
            f.seek(start_char)
            content = f.read(end_char - start_char)
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

# We will need a factory to inject the session_id
def get_read_file_chunk_tool(session_id: str) -> Tool:
    schema = {
        "type": "function",
        "function": {
            "name": "read_file_chunk",
            "description": "Read a specific chunk of a truncated artifact file from start_char to end_char.",
            "parameters": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "The absolute path to the file to read."
                    },
                    "start_char": {
                        "type": "integer",
                        "description": "The character index to start reading from."
                    },
                    "end_char": {
                        "type": "integer",
                        "description": "The character index to stop reading at."
                    }
                },
                "required": ["file_path", "start_char", "end_char"]
            }
        }
    }
    
    # Create a partial-like wrapper that injects session_id
    def wrapped_func(file_path: str, start_char: int, end_char: int):
        return read_file_chunk_func(file_path, start_char, end_char, session_id)
        
    return Tool(
        name="read_file_chunk",
        description="Read a specific chunk of a truncated artifact file.",
        func=wrapped_func,
        schema=schema,
        requires_approval=False
    )

def get_search_tools_tool(agent) -> Tool:
    def search_tools_func(query: str) -> str:
        """Search the tool registry for relevant tools."""
        tools = agent.tool_registry.search(query)
        if not tools:
            return "No matching tools found."
        
        result = "Found the following tools. Their schemas have been automatically injected into your context for the next turn:\n\n"
        
        existing_names = {t.name for t in agent.tools}
        for t in tools:
            if t.name not in existing_names:
                agent.tools.append(t)
            result += f"- **{t.name}**: {t.description}\n"
            
        return result

    schema = {
        "type": "function",
        "function": {
            "name": "search_tools",
            "description": "Search the tool registry for tools that can help with a specific task.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The task or functionality you need a tool for."
                    }
                },
                "required": ["query"]
            }
        }
    }
    
    # Needs a hack to inject the found tools into the Agent's active tools.
    # The Runner will handle parsing the tool execution to append to `agent.tools`.
    
    return Tool(
        name="search_tools",
        description="Search the tool registry for tools that can help with a specific task.",
        func=search_tools_func,
        schema=schema
    )
