import json
import numpy as np
from pathlib import Path
from loguru import logger
from config import settings
from typing import List, Dict, Any


class VectorStore:
    """Pure-Python vector store backed by a JSON file. No C++ required."""

    def __init__(self, path: str):
        self._file = Path(path) / "vectors.json"
        self._file.parent.mkdir(parents=True, exist_ok=True)
        self._docs: List[Dict] = json.loads(self._file.read_text()) if self._file.exists() else []

    def _save(self):
        self._file.write_text(json.dumps(self._docs))

    def upsert(self, doc_id: str, texts: List[str], metadatas: List[Dict], embeddings: List[List[float]]):
        # Remove old chunks for this doc
        self._docs = [d for d in self._docs if d["meta"].get("doc_id") != doc_id]
        for text, meta, emb in zip(texts, metadatas, embeddings):
            self._docs.append({"text": text, "meta": meta, "emb": emb})
        self._save()

    def search(self, query_emb: List[float], top_k: int = 5) -> List[Dict]:
        if not self._docs:
            return []
        embs = np.array([d["emb"] for d in self._docs], dtype=np.float32)
        q = np.array(query_emb, dtype=np.float32)
        # Cosine similarity
        norm_embs = embs / (np.linalg.norm(embs, axis=1, keepdims=True) + 1e-10)
        norm_q = q / (np.linalg.norm(q) + 1e-10)
        sims = norm_embs @ norm_q
        top_idx = np.argsort(sims)[::-1][:top_k]
        return [
            {"content": self._docs[i]["text"], "metadata": self._docs[i]["meta"], "similarity": float(sims[i])}
            for i in top_idx if sims[i] > 0.3
        ]

    def delete(self, doc_id: str):
        self._docs = [d for d in self._docs if d["meta"].get("doc_id") != doc_id]
        self._save()

    def count(self) -> int:
        return len(self._docs)


class RAGService:
    def __init__(self):
        self._store = VectorStore(settings.chroma_path)

    async def add_documents(self, chunks: List[str], doc_id: str, filename: str, category: str = "general") -> int:
        if not chunks:
            return 0
        from services.embedding_service import embed_texts
        embeddings = await embed_texts(chunks)
        metadatas = [{"doc_id": doc_id, "filename": filename, "category": category, "chunk_index": i} for i in range(len(chunks))]
        self._store.upsert(doc_id, chunks, metadatas, embeddings)
        logger.info(f"Stored {len(chunks)} chunks for {filename}")
        return len(chunks)

    async def build_context(self, query: str) -> tuple[str, List[str]]:
        from services.embedding_service import embed_query
        query_emb = await embed_query(query)
        hits = self._store.search(query_emb, top_k=settings.rag_top_k)
        if not hits:
            return "", []
        sources = list({h["metadata"]["filename"] for h in hits})
        context = "\n\n---\n\n".join(f"[Source: {h['metadata']['filename']}]\n{h['content']}" for h in hits)
        return context, sources

    def delete_document(self, doc_id: str):
        self._store.delete(doc_id)

    def get_stats(self) -> Dict[str, Any]:
        return {"total_chunks": self._store.count()}


rag_service = RAGService()
