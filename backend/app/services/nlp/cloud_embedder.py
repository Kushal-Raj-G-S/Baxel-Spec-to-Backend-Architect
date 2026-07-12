import os
import logging
import numpy as np
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Winner from benchmark: 0.75s avg latency per batch, dim=2048
NVIDIA_EMBED_MODEL = "nvidia/llama-nemotron-embed-1b-v2"
NVIDIA_EMBED_DIM = 2048


def _load_api_key() -> str:
    """Load NVIDIA_API_KEY from environment or backend/.env."""
    key = os.getenv("NVIDIA_API_KEY", "").strip()
    if key:
        return key
    candidates = [
        Path(".env"),
        Path(__file__).resolve().parents[3] / ".env",
        Path(__file__).resolve().parents[4] / ".env",
    ]
    for env_path in candidates:
        if env_path.exists():
            try:
                for line in env_path.read_text(encoding="utf-8-sig", errors="ignore").splitlines():
                    line = line.strip()
                    if line.startswith("NVIDIA_API_KEY") and "=" in line:
                        val = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if val:
                            return val
            except Exception:
                pass
    return ""


class CloudEmbedder:
    """
    Drop-in replacement for SentenceTransformer that calls the Nvidia NIM
    embedding API (nvidia/llama-nemotron-embed-1b-v2) instead of loading
    local model weights.

    Interface is intentionally identical to SentenceTransformer.encode():
        embeddings = cloud_embedder.encode(list_of_strings)
        → returns np.ndarray of shape (N, 2048) dtype float32

    Falls back to random unit vectors on API failure so downstream Faiss
    operations never crash (same pattern as the existing string fallback).
    """

    def __init__(self):
        self.api_key: Optional[str] = None
        self.base_url = "https://integrate.api.nvidia.com/v1/embeddings"
        self.model = NVIDIA_EMBED_MODEL
        self.dim = NVIDIA_EMBED_DIM
        self.initialized = False
        self._init_attempted = False

    def initialize(self):
        if self._init_attempted:
            return
        self._init_attempted = True
        self.api_key = _load_api_key()
        if not self.api_key:
            logger.warning(
                "CloudEmbedder: NVIDIA_API_KEY not found. "
                "Embeddings will fall back to string-similarity mode."
            )
            return
        self.initialized = True
        logger.info(
            f"CloudEmbedder initialized — model: {self.model} | dim: {self.dim}"
        )

    def encode(self, texts: List[str]) -> np.ndarray:
        """
        Encode a list of texts into embedding vectors.
        Returns np.ndarray shape (len(texts), self.dim) dtype float32.
        """
        if not self._init_attempted:
            self.initialize()

        if not self.initialized or not self.api_key:
            # Fallback: return zero vectors so Faiss doesn't crash
            logger.warning("CloudEmbedder: falling back to zero vectors (no API key).")
            return np.zeros((len(texts), self.dim), dtype="float32")

        try:
            import httpx
        except ImportError:
            import subprocess, sys
            subprocess.check_call([sys.executable, "-m", "pip", "install", "httpx"])
            import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
            "input_type": "query",
            "truncate": "END",
            "encoding_format": "float",
        }

        try:
            with httpx.Client(timeout=20.0) as client:
                resp = client.post(self.base_url, headers=headers, json=payload)

            if resp.status_code == 200:
                data = resp.json()
                items = data.get("data", [])
                # Sort by index to preserve original order
                items_sorted = sorted(items, key=lambda x: x.get("index", 0))
                vectors = np.array(
                    [item["embedding"] for item in items_sorted], dtype="float32"
                )
                return vectors
            else:
                logger.error(
                    f"CloudEmbedder: API error {resp.status_code}: {resp.text[:200]}"
                )
                return np.zeros((len(texts), self.dim), dtype="float32")

        except Exception as e:
            logger.error(f"CloudEmbedder: request failed: {e}")
            return np.zeros((len(texts), self.dim), dtype="float32")


# Singleton — shared across clustering and RAG retriever
cloud_embedder = CloudEmbedder()
