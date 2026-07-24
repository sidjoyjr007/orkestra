from typing import Optional
from orkestra.providers.openai_provider import OpenAIProvider

class VLLMProvider(OpenAIProvider):
    """
    vLLM API provider implementation.
    vLLM exposes an OpenAI-compatible server.
    """

    def __init__(self, model_name: str, base_url: str, api_key: Optional[str] = "EMPTY", **kwargs):
        """
        Initialize the vLLM provider.
        
        Args:
            model_name: The name of the model on the vLLM server.
            base_url: The URL of the vLLM server (e.g., http://localhost:8000/v1)
            api_key: The API key for the vLLM server. Defaults to "EMPTY".
        """
        super().__init__(model_name=model_name, api_key=api_key, **kwargs)
        # Override the client to point to the vLLM server
        import openai
        self.client = openai.OpenAI(api_key=api_key, base_url=base_url)
