import os
from typing import Any, Dict, Iterator, List, Optional
from orkestra.providers.openai_provider import OpenAIProvider

class HuggingFaceProvider(OpenAIProvider):
    """
    HuggingFace API provider implementation.
    Uses HuggingFace's OpenAI compatible Messages API via the Hub.
    """

    def __init__(self, model_name: str, api_key: Optional[str] = None, **kwargs):
        """
        Initialize the HuggingFace provider.
        
        Args:
            model_name: The name of the model on HF Hub (e.g., 'meta-llama/Meta-Llama-3-8B-Instruct').
            api_key: The HF Token. Defaults to checking the HF_TOKEN environment variable.
        """
        resolved_api_key = api_key or os.environ.get("HF_TOKEN")
        super().__init__(model_name=model_name, api_key=resolved_api_key, **kwargs)
        import openai
        # HuggingFace Serverless Inference API supports the OpenAI protocol at this endpoint:
        self.client = openai.OpenAI(
            base_url="https://api-inference.huggingface.co/v1/",
            api_key=resolved_api_key
        )
