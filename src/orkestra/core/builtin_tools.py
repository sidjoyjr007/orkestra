import os
from orkestra.core.tools import HostTool

def read_file_chunk_func(file_path: str, start_char: int, end_char: int, artifact_dir: str) -> str:
    """Read a specific chunk of a file. Only allowed within the session's artifact directory."""
    allowed_dir = os.path.abspath(artifact_dir)
    target_path = os.path.abspath(file_path)
    
    # Sandboxing check
    if not target_path.startswith(allowed_dir):
        return f"Error: Permission denied. Can only read files inside {allowed_dir}"
        
    if not os.path.exists(target_path):
        return f"Error: File not found at {target_path}. The temporary artifact may have been deleted by the OS. Please autonomously call the original tool again to re-fetch the content, and then try reading it again."
        
    try:
        file_size = os.path.getsize(target_path)
        
        # Support negative indexing (e.g. -2000 means 2000 chars from the end)
        if start_char < 0:
            start_char = max(0, file_size + start_char)
        if end_char < 0:
            end_char = max(0, file_size + end_char)
            
        # If end_char is still less than start_char, it's invalid
        if end_char <= start_char:
            return "Error: end_char must be greater than start_char"
            
        with open(target_path, "r", encoding="utf-8") as f:
            f.seek(start_char)
            content = f.read(end_char - start_char)
            return content
    except Exception as e:
        return f"Error reading file: {str(e)}"

# We will need a factory to inject the artifact_dir
def get_read_file_chunk_tool(artifact_dir: str) -> HostTool:
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
    
    # Create a partial-like wrapper that injects artifact_dir
    def wrapped_func(file_path: str, start_char: int, end_char: int, **kwargs):
        return read_file_chunk_func(file_path, start_char, end_char, artifact_dir)
        
    return HostTool(
        name="read_file_chunk",
        description="Read a specific chunk of a truncated artifact file.",
        func=wrapped_func,
        schema=schema,
        requires_approval=False
    )

def get_search_tools_tool(agent) -> HostTool:
    def search_tools_func(query: str, **kwargs) -> str:
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
    
    return HostTool(
        name="search_tools",
        description="Search the tool registry for tools that can help with a specific task.",
        func=search_tools_func,
        schema=schema
    )
