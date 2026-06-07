"""
ChromaDB-based memory store for FutureWeave.
Stores user goals, previous simulations, preferences, risk profiles, and follow-up pivots.
"""
import json
import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class MemoryStore:
    def __init__(self, persist_dir: str = None):
        self.persist_dir = persist_dir or os.path.join(os.path.dirname(__file__), "..", ".memory_store")
        self._collection = None
        self._client = None

    def _ensure_initialized(self):
        if self._collection is not None:
            return
        try:
            import chromadb
            self._client = chromadb.PersistentClient(path=self.persist_dir)
            self._collection = self._client.get_or_create_collection(
                name="futureweave_memory",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("[Memory] ChromaDB initialized at %s", self.persist_dir)
        except ImportError:
            logger.warning("[Memory] chromadb not available — using in-memory dict store")
            self._collection = _DictCollection()

    def store_simulation(
        self,
        user_id: str,
        decision: str,
        simulation_id: str,
        result: dict,
        metadata: Optional[dict] = None,
    ):
        self._ensure_initialized()
        doc_id = f"sim_{simulation_id}"

        document = json.dumps({
            "decision": decision,
            "result_summary": {
                "primary_path": result.get("synthesis", {}).get("recommendation", {}).get("primary_path", ""),
                "top_income": max(
                    (v.get("income", 0) for v in result.get("agent_outputs", {}).get("economic", {}).get("output", {}).get("salary_growth_forecast", [])),
                    default=0,
                ),
            },
            "timestamp": datetime.now().isoformat(),
        })

        metadatas = {
            "type": "simulation",
            "user_id": user_id,
            "decision": decision[:200],
            "simulation_id": simulation_id,
            "timestamp": datetime.now().isoformat(),
            **(metadata or {}),
        }

        try:
            from memory.embeddings import embed_text
            embedding = embed_text(f"{decision} {document}")
            self._collection.add(
                documents=[document],
                embeddings=[embedding],
                metadatas=[metadatas],
                ids=[doc_id],
            )
            logger.info("[Memory] Stored simulation %s", doc_id)
        except Exception as exc:
            logger.warning("[Memory] Failed to store simulation: %s", exc)

    def store_user_preferences(self, user_id: str, preferences: dict):
        self._ensure_initialized()
        doc_id = f"prefs_{user_id}"
        document = json.dumps(preferences)
        try:
            from memory.embeddings import embed_text
            embedding = embed_text(json.dumps(preferences))
            self._collection.add(
                documents=[document],
                embeddings=[embedding],
                metadatas=[{"type": "preferences", "user_id": user_id, "timestamp": datetime.now().isoformat()}],
                ids=[doc_id],
            )
        except Exception as exc:
            logger.warning("[Memory] Failed to store preferences: %s", exc)

    def query(self, query_text: str, n_results: int = 5, filter_type: Optional[str] = None) -> List[dict]:
        self._ensure_initialized()
        try:
            from memory.embeddings import embed_text
            query_embedding = embed_text(query_text)
            where = {"type": filter_type} if filter_type else None
            results = self._collection.query(
                query_embeddings=[query_embedding],
                n_results=n_results,
                where=where,
            )
            return self._format_results(results)
        except Exception as exc:
            logger.warning("[Memory] Query failed: %s", exc)
            return []

    def query_similar_decisions(self, decision: str, n_results: int = 3) -> List[dict]:
        return self.query(decision, n_results=n_results, filter_type="simulation")

    def _format_results(self, results: Any) -> List[dict]:
        formatted = []
        if not results or not results.get("ids"):
            return formatted
        for i in range(len(results["ids"][0])):
            formatted.append({
                "id": results["ids"][0][i],
                "document": results["documents"][0][i] if results.get("documents") else "",
                "metadata": results["metadatas"][0][i] if results.get("metadatas") else {},
                "distance": results["distances"][0][i] if results.get("distances") else 0,
            })
        return formatted


class _DictCollection:
    def __init__(self):
        self.data: Dict[str, dict] = {}

    def get_or_create_collection(self, **kwargs):
        return self

    def add(self, documents, embeddings, metadatas, ids):
        for i, doc_id in enumerate(ids):
            self.data[doc_id] = {
                "document": documents[i] if isinstance(documents, list) else documents,
                "embedding": embeddings[i] if isinstance(embeddings, list) else embeddings,
                "metadata": metadatas[i] if isinstance(metadatas, list) else metadatas,
            }

    def query(self, query_embeddings, n_results=5, where=None):
        ids = []
        documents = []
        metadatas = []
        distances = []

        sorted_items = sorted(
            self.data.items(),
            key=lambda x: _cosine_sim(query_embeddings[0], x[1].get("embedding", [])),
            reverse=True,
        )[:n_results]

        for doc_id, item in sorted_items:
            if where and item.get("metadata", {}).get("type") != where.get("type"):
                continue
            ids.append([doc_id])
            documents.append([item["document"]])
            metadatas.append([item["metadata"]])
            distances.append([1 - _cosine_sim(query_embeddings[0], item.get("embedding", []))])

        return {"ids": ids, "documents": documents, "metadatas": metadatas, "distances": distances}


def _cosine_sim(a: List[float], b: List[float]) -> float:
    if not a or not b:
        return 0
    dot = sum(x*y for x, y in zip(a, b))
    na = sum(x*x for x in a) ** 0.5
    nb = sum(x*x for x in b) ** 0.5
    return dot / (na * nb) if na * nb > 0 else 0


_default_store: Optional[MemoryStore] = None


def get_memory_store() -> MemoryStore:
    global _default_store
    if _default_store is None:
        _default_store = MemoryStore()
    return _default_store
