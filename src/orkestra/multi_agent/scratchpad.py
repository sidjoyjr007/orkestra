import json
from typing import Dict, Any, Optional
from orkestra.core.tools import Tool
from orkestra.core.telemetry import get_logger

logger = get_logger("orkestra.multi_agent.scratchpad")

class SharedScratchpad:
    """
    A global key-value store that persists across handoffs and sub-agent delegations.
    """
    def __init__(self):
        self._data: Dict[str, Any] = {}

    def get(self, key: str) -> Optional[Any]:
        return self._data.get(key)

    def set(self, key: str, value: Any):
        self._data[key] = value

    def delete(self, key: str):
        if key in self._data:
            del self._data[key]

    def list_keys(self) -> list[str]:
        return list(self._data.keys())

    def to_dict(self) -> dict:
        return self._data.copy()

    def from_dict(self, data: dict):
        self._data = data.copy()

class ReadScratchpadTool(Tool):
    def __init__(self, scratchpad: SharedScratchpad):
        schema = {
            "type": "function",
            "function": {
                "name": "read_scratchpad",
                "description": "Read a value from the shared global scratchpad.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "The key to read."
                        }
                    },
                    "required": ["key"]
                }
            }
        }
        super().__init__(
            name="read_scratchpad",
            description="Read a value from the shared global scratchpad.",
            func=self.run,
            schema=schema
        )
        self.scratchpad = scratchpad

    def run(self, key: str, **kwargs) -> str:
        value = self.scratchpad.get(key)
        if value is None:
            # Maybe they don't know the keys, so list them
            keys = self.scratchpad.list_keys()
            return f"Key '{key}' not found. Available keys: {keys}"
        
        if isinstance(value, (dict, list)):
            return json.dumps(value)
        return str(value)

    async def arun(self, key: str, **kwargs) -> str:
        return self.run(key, **kwargs)

class WriteScratchpadTool(Tool):
    def __init__(self, scratchpad: SharedScratchpad):
        schema = {
            "type": "function",
            "function": {
                "name": "write_scratchpad",
                "description": "Write a value to the shared global scratchpad to share it with other agents.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string",
                            "description": "The key to write to."
                        },
                        "value": {
                            "type": "string",
                            "description": "The string value to save."
                        }
                    },
                    "required": ["key", "value"]
                }
            }
        }
        super().__init__(
            name="write_scratchpad",
            description="Write a value to the shared global scratchpad.",
            func=self.run,
            schema=schema
        )
        self.scratchpad = scratchpad

    def run(self, key: str, value: str, **kwargs) -> str:
        self.scratchpad.set(key, value)
        logger.info(f"Scratchpad updated: '{key}'")
        return f"Successfully wrote '{key}' to the shared scratchpad."

    async def arun(self, key: str, value: str, **kwargs) -> str:
        return self.run(key, value, **kwargs)
