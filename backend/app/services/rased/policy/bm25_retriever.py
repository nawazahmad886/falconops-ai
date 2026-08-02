"""
BM25 retrieval over the SOP corpus — the default retriever, and the one the
demo must never fail to have available. rank-bm25 is pure Python scoring
against an in-process token index built once at construction time; no
external service, no network call, no provisioning step.
"""
import re
from typing import List, Optional

from rank_bm25 import BM25Okapi

from .corpus_loader import SOPSection, load_corpus
from .retriever import SOPRetriever

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _tokenize(text: str) -> List[str]:
    return _TOKEN_RE.findall(text.lower())


class BM25Retriever(SOPRetriever):
    def __init__(self, sections: Optional[List[SOPSection]] = None):
        self.sections = sections if sections is not None else load_corpus()
        corpus_tokens = [_tokenize(f"{s.title} {s.text}") for s in self.sections]
        self._index = BM25Okapi(corpus_tokens) if corpus_tokens else None

    def search(self, query: str, top_k: int = 3) -> List[SOPSection]:
        if self._index is None or not self.sections:
            return []
        scores = self._index.get_scores(_tokenize(query))
        ranked = sorted(zip(self.sections, scores), key=lambda pair: pair[1], reverse=True)
        return [section for section, score in ranked[:top_k] if score > 0]


__all__ = ["BM25Retriever"]
