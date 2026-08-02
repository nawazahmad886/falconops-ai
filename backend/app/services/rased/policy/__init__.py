from .corpus_loader import SOPSection, load_corpus
from .retriever import SOPRetriever
from .bm25_retriever import BM25Retriever
from .vector_retriever import VectorRetriever


def get_retriever() -> SOPRetriever:
    from ..config import SOP_RETRIEVER_BACKEND
    if SOP_RETRIEVER_BACKEND == "vector":
        return VectorRetriever()
    return BM25Retriever()


__all__ = ["SOPSection", "load_corpus", "SOPRetriever", "BM25Retriever", "VectorRetriever", "get_retriever"]
