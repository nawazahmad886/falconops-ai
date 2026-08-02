"""
Loads the SOP corpus from backend/data/sop_corpus/*.md into addressable
sections with stable IDs, cached at module scope after the first load rather
than re-parsed on every retrieval call.

Section boundary convention: a level-2 markdown heading of the form
"## [<SECTION_ID>] <Title>" starts a new section; everything up to the next
such heading (or end of file) is that section's body. The bracketed ID is
the stable identifier PolicyDecision.citations points at — it does not shift
if sections are reordered or new ones are inserted, unlike positional
numbering.
"""
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

SOP_CORPUS_DIR = Path(__file__).resolve().parents[4] / "data" / "sop_corpus"

_SECTION_HEADING_RE = re.compile(r"^##\s+\[([A-Za-z0-9\-]+)\]\s+(.+)$", re.MULTILINE)


@dataclass
class SOPSection:
    document_id: str
    section_id: str
    title: str
    text: str


def _document_id_from_filename(path: Path) -> str:
    return path.stem


def _parse_document(path: Path) -> List[SOPSection]:
    document_id = _document_id_from_filename(path)
    content = path.read_text(encoding="utf-8")

    matches = list(_SECTION_HEADING_RE.finditer(content))
    sections: List[SOPSection] = []
    for i, match in enumerate(matches):
        section_id, title = match.group(1), match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(content)
        sections.append(SOPSection(
            document_id=document_id,
            section_id=section_id,
            title=title,
            text=content[start:end].strip(),
        ))
    return sections


_cache: Optional[List[SOPSection]] = None


def load_corpus(force_reload: bool = False) -> List[SOPSection]:
    global _cache
    if _cache is not None and not force_reload:
        return _cache

    sections: List[SOPSection] = []
    if SOP_CORPUS_DIR.exists():
        for path in sorted(SOP_CORPUS_DIR.glob("*.md")):
            sections.extend(_parse_document(path))
    _cache = sections
    return sections


__all__ = ["SOPSection", "load_corpus", "SOP_CORPUS_DIR"]
