from database import get_db
from loguru import logger
from typing import List, Dict, Any
import uuid


class RAGService:
    """Keyword-based RAG using Firestore. No embeddings needed — works on Vercel."""

    def _score(self, text: str, keywords: set) -> int:
        t = text.lower()
        return sum(1 for k in keywords if k in t)

    def _extract_keywords(self, query: str) -> set:
        stop = {'what','is','the','a','an','in','of','to','for','how','does',
                'do','can','i','me','my','and','or','with','are','was','were',
                'be','been','being','have','has','had','will','would','could',
                'should','about','if','this','that','which','when','where'}
        words = set(query.lower().split()) - stop
        return {w for w in words if len(w) > 2}

    def add_documents(self, chunks: List[str], doc_id: str, filename: str, category: str = "general") -> int:
        db = get_db()
        batch = db.batch()
        count = 0
        for i, chunk in enumerate(chunks):
            ref = db.collection('vectors').document(f"{doc_id}_chunk_{i}")
            batch.set(ref, {
                'doc_id': doc_id,
                'filename': filename,
                'category': category,
                'chunk_index': i,
                'text': chunk,
            })
            count += 1
            if count % 400 == 0:  # Firestore batch limit is 500
                batch.commit()
                batch = db.batch()
        batch.commit()
        logger.info(f"Stored {count} chunks for {filename}")
        return count

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        keywords = self._extract_keywords(query)
        if not keywords:
            return []
        db = get_db()
        docs = list(db.collection('vectors').limit(500).stream())
        scored = []
        for doc in docs:
            d = doc.to_dict()
            score = self._score(d.get('text', ''), keywords)
            if score > 0:
                scored.append((score, d))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [{'content': d['text'], 'metadata': d, 'score': s} for s, d in scored[:top_k]]

    def build_context(self, query: str) -> tuple[str, List[str]]:
        hits = self.search(query)
        if not hits:
            return "", []
        sources = list({h['metadata']['filename'] for h in hits})
        context = "\n\n---\n\n".join(f"[Source: {h['metadata']['filename']}]\n{h['content']}" for h in hits)
        return context, sources

    def delete_document(self, doc_id: str):
        db = get_db()
        docs = db.collection('vectors').where('doc_id', '==', doc_id).stream()
        batch = db.batch()
        for doc in docs:
            batch.delete(doc.reference)
        batch.commit()

    def get_stats(self) -> Dict[str, Any]:
        try:
            db = get_db()
            count = len(list(db.collection('vectors').limit(1000).stream()))
            return {"total_chunks": count}
        except Exception:
            return {"total_chunks": 0}


rag_service = RAGService()
