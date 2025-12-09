"""
Ollama API client wrapper.
"""
import httpx
import json
from typing import Optional, List, Dict, Any
from core.config import (
    OLLAMA_BASE_URL,
    OLLAMA_MIXTRAL_MODEL,
    OLLAMA_LLAVA_MODEL,
    OLLAMA_EMBED_MODEL,
    LLM_TEMPERATURE,
    LLM_MAX_TOKENS,
)


class OllamaClient:
    """Client for interacting with Ollama models."""
    
    def __init__(self, base_url: str = OLLAMA_BASE_URL):
        self.base_url = base_url
        self.client = httpx.Client(timeout=300.0)  # 5 min timeout for long operations
    
    def _call_model(
        self,
        model: str,
        prompt: str,
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_TOKENS,
        stream: bool = False,
    ) -> str:
        """Generic method to call any Ollama model."""
        url = f"{self.base_url}/api/generate"
        payload = {
            "model": model,
            "prompt": prompt,
            "options": {
                "temperature": temperature,
                "num_predict": max_tokens,
            },
            "stream": stream,
        }
        
        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("response", "")
        except Exception as e:
            raise Exception(f"Ollama API error: {str(e)}")
    
    def call_mixtral(
        self,
        prompt: str,
        temperature: float = LLM_TEMPERATURE,
        max_tokens: int = LLM_MAX_TOKENS,
    ) -> str:
        """Call Mixtral model for reasoning tasks."""
        return self._call_model(
            OLLAMA_MIXTRAL_MODEL,
            prompt,
            temperature,
            max_tokens,
        )
    
    def call_llava(self, prompt: str, image_path: Optional[str] = None) -> str:
        """Call LLaVA model for vision tasks (Phase 2)."""
        # For Phase 2 implementation
        raise NotImplementedError("LLaVA integration coming in Phase 2")
    
    def generate_embedding(self, text: str) -> List[float]:
        """Generate embedding vector for text (Phase 4 - RAG)."""
        url = f"{self.base_url}/api/embeddings"
        payload = {
            "model": OLLAMA_EMBED_MODEL,
            "prompt": text,
        }
        
        try:
            response = self.client.post(url, json=payload)
            response.raise_for_status()
            result = response.json()
            return result.get("embedding", [])
        except Exception as e:
            raise Exception(f"Ollama embedding error: {str(e)}")


# Global Ollama client instance
ollama = OllamaClient()

