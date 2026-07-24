def _format_openai_tools(tools: list) -> list:
    """Format unified tools into OpenAI format."""
    if not tools:
        return None
    formatted = []
    for t in tools:
        # Assuming t is a dictionary with 'name', 'description', 'parameters'
        formatted.append({
            "type": "function",
            "function": {
                "name": t.get("name"),
                "description": t.get("description"),
                "parameters": t.get("parameters", {})
            }
        })
    return formatted
