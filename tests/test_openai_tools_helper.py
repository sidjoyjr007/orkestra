from orkestra.providers.openai_tools_helper import _format_openai_tools

def test_format_openai_tools_empty():
    assert _format_openai_tools(None) is None
    assert _format_openai_tools([]) is None

def test_format_openai_tools_valid():
    tools = [
        {"name": "tool1", "description": "desc1", "parameters": {"type": "object"}},
        {"name": "tool2", "description": "desc2"} # missing parameters
    ]
    formatted = _format_openai_tools(tools)
    
    assert len(formatted) == 2
    assert formatted[0]["type"] == "function"
    assert formatted[0]["function"]["name"] == "tool1"
    assert formatted[0]["function"]["description"] == "desc1"
    assert formatted[0]["function"]["parameters"] == {"type": "object"}
    
    assert formatted[1]["function"]["name"] == "tool2"
    assert formatted[1]["function"]["parameters"] == {}
