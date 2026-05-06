import httpx
from typing import List
from config import settings

EMBED_MODEL = "nomic-embed-text"


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed a list of texts using Ollama's embedding API."""
    embeddings = []
    async with httpx.AsyncClient(timeout=60) as client:
        for text in texts:
            resp = await client.post(
                f"{settings.ollama_base_url}/api/embeddings",
                json={"model": EMBED_MODEL, "prompt": text},
            )
            resp.raise_for_status()
            embeddings.append(resp.json()["embedding"])
    return embeddings


async def embed_query(query: str) -> List[float]:
    results = await embed_texts([query])
    return results[0]
