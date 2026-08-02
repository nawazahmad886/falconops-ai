"""
SOPRetriever interface. BM25Retriever is the default and must work with zero
external services (~40 sections doesn't need embeddings, and this removes
any vector-store dependency from the demo's critical path). VectorRetriever
sits behind the same interface as a config-selected optional upgrade.
"""
from abc import ABC, abstractmethod
from typing import List

from .corpus_loader import SOPSection


class SOPRetriever(ABC):
    @abstractmethod
    def search(self, query: str, top_k: int = 3) -> List[SOPSection]:
        raise NotImplementedError


__all__ = ["SOPRetriever"]
