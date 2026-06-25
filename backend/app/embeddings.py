"""Embeddings for the knowledge base (and, later, control-matching).

Anthropic has no embeddings API; Voyage AI is its recommended partner. Calls
Voyage's REST API directly via httpx rather than its official SDK -- that
SDK pulls in langchain-text-splitters, tokenizers, pillow, and ffmpeg-python
(it's built for multimodal/LangChain use cases), which is an unjustified
dependency footprint for a backend that only needs text embeddings.

Every caller must tolerate `None` -- without VOYAGE_API_KEY configured, the
knowledge base falls back to Postgres full-text/ILIKE search instead of
vector similarity. Never raise here; embeddings are an enhancement, not a
dependency callers should crash without.
"""

import httpx

from app.config import settings
from app.models import EMBEDDING_DIM

API_URL = "https://api.voyageai.com/v1/embeddings"
MODEL = "voyage-3"


def embed_text(text: str) -> list[float] | None:
    results = embed_batch([text])
    return results[0] if results else None


def embed_batch(texts: list[str]) -> list[list[float] | None] | None:
    if not settings.voyage_api_key or not texts:
        return None

    try:
        response = httpx.post(
            API_URL,
            headers={"Authorization": f"Bearer {settings.voyage_api_key}"},
            json={"input": texts, "model": MODEL, "input_type": "document"},
            timeout=15,
        )
        response.raise_for_status()
        data = response.json()["data"]
    except Exception:
        # Embeddings are a nice-to-have for search quality, not a hard
        # dependency -- a Voyage outage should degrade to keyword search,
        # not break ingestion.
        return None

    embeddings = [d["embedding"] for d in sorted(data, key=lambda d: d["index"])]
    assert all(len(e) == EMBEDDING_DIM for e in embeddings), (
        f"voyage-3 returned unexpected dimension; expected {EMBEDDING_DIM}"
    )
    return embeddings
