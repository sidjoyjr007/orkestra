import pytest
import os
from unittest.mock import patch, MagicMock
from orkestra.providers.vllm_provider import VLLMProvider
from orkestra.providers.huggingface_provider import HuggingFaceProvider

def test_vllm_provider_initialization():
    with patch("openai.OpenAI") as mock_openai:
        provider = VLLMProvider(model_name="test-model", base_url="http://localhost:8000/v1")
        assert provider.model_name == "test-model"
        
        # Verify it passed the correct kwargs to the underlying OpenAI client
        mock_openai.assert_called_once_with(api_key="EMPTY", base_url="http://localhost:8000/v1")

def test_huggingface_provider_initialization():
    with patch("openai.OpenAI") as mock_openai:
        provider = HuggingFaceProvider(model_name="test-hf-model", api_key="hf_test_key")
        assert provider.model_name == "test-hf-model"
        
        # Verify it passed the correct kwargs to the underlying OpenAI client
        mock_openai.assert_called_once_with(api_key="hf_test_key", base_url="https://api-inference.huggingface.co/v1/")

def test_huggingface_provider_fallback_env_token():
    with patch.dict(os.environ, {"HF_TOKEN": "hf_env_token"}):
        with patch("openai.OpenAI") as mock_openai:
            provider = HuggingFaceProvider(model_name="test-hf-model", api_key=None)
            
            # Verify it used the environment variable
            mock_openai.assert_called_once_with(api_key="hf_env_token", base_url="https://api-inference.huggingface.co/v1/")
