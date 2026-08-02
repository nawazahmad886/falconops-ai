"""
Optional embedding-based retriever over the SOP corpus, behind the same
SOPRetriever interface as BM25Retriever. Not the default (the demo must
never depend on a vector store being provisioned) — selected only via
config.SOP_RETRIEVER_BACKEND == "vector". Uses sentence-transformers, which
is already pinned in requirements.txt for other subsystems, so choosing this
backend adds no new dependency of its own. Cosine similarity is computed
in-process against a NumPy array built at first use; no vector database.
"""
import logging
from typing import List, Optional

from .corpus_loader import SOPSection, load_corpus
from .retriever import SOPRetriever

logger = logging.getLogger(__name__)

DEFAULT_MODEL_NAME = "all-MiniLM-L6-v2"


class VectorRetriever(SOPRetriever):
    def __init__(self, sections: Optional[List[SOPSection]] = None, model_name: str = DEFAULT_MODEL_NAME):
        self.sections = sections if sections is not None else load_corpus()
        self._model_name = model_name
        self._model = None
        self._embeddings = None

    def _ensure_model(self) -> None:
        if self._model is not None:
            return
        from sentence_transformers import SentenceTransformer
        self._model = SentenceTransformer(self._model_name)
        corpus_texts = [f"{s.title} {s.text}" for s in self.sections]
        self._embeddings = self._model.encode(corpus_texts) if corpus_texts else None

    def search(self, query: str, top_k: int = 3) -> List[SOPSection]:
        if not self.sections:
            return []
        try:
            self._ensure_model()
        except Exception as exc:
            logger.warning(f"vector retriever unavailable, returning no results: {exc}")
            return []
        if self._embeddings is None:
            return []

        import numpy as np
        query_embedding = self._model.encode([query])[0]
        norms = (self._embeddings ** 2).sum(axis=1) ** 0.5 * (query_embedding ** 2).sum() ** 0.5
        scores = (self._embeddings @ query_embedding) / (norms + 1e-9)
        ranked = sorted(zip(self.sections, scores), key=lambda pair: pair[1], reverse=True)
        return [section for section, _ in ranked[:top_k]]


__all__ = ["VectorRetriever", "DEFAULT_MODEL_NAME"]
