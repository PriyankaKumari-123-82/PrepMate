import re
from dataclasses import dataclass


@dataclass
class TextChunk:
    text: str
    page_start: int
    page_end: int
    section: str | None = None


def chunk_pages(pages: list[tuple[int, str]], size: int = 2200, overlap: int = 250) -> list[TextChunk]:
    """Chunk pages without losing page provenance; chunks never cross a page boundary."""
    chunks: list[TextChunk] = []
    for page_no, raw in pages:
        text = re.sub(r"[ \t]+", " ", raw).strip()
        if not text:
            continue
        heading = next((line.strip() for line in raw.splitlines() if 3 < len(line.strip()) < 100), None)
        start = 0
        while start < len(text):
            end = min(len(text), start + size)
            if end < len(text):
                boundary = text.rfind(". ", start + size // 2, end)
                if boundary > start:
                    end = boundary + 1
            chunks.append(TextChunk(text[start:end].strip(), page_no, page_no, heading))
            if end >= len(text):
                break
            start = max(start + 1, end - overlap)
    return chunks

