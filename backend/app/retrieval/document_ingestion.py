"""Controlled TXT/PDF/DOCX ingestion for the classical IR corpus."""

from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Protocol

from backend.app.retrieval.preprocessing import preprocess_for_retrieval
from backend.app.retrieval.schemas import KnowledgeChunk, KnowledgeDocumentType


SUPPORTED_EXTENSIONS = frozenset({".txt", ".pdf", ".docx"})


class DocumentIngestionError(ValueError):
    """Raised when a controlled document cannot be safely ingested."""


class UnsupportedDocumentError(DocumentIngestionError):
    pass


class KnowledgeChunkRepository(Protocol):
    def get_knowledge_chunks_by_source(
        self, source_document_id: str
    ) -> list[KnowledgeChunk]: ...

    def replace_knowledge_chunks(
        self, source_document_id: str, chunks: list[KnowledgeChunk]
    ) -> list[KnowledgeChunk]: ...


@dataclass(frozen=True)
class ExtractedSection:
    title: str | None
    content: str
    metadata: dict[str, object]


@dataclass(frozen=True)
class IngestionResult:
    source_document_id: str
    source_title: str
    chunks_created_or_updated: int
    duplicate_unchanged: bool


def _clean_text(text: str) -> str:
    return re.sub(r"[ \t]+", " ", re.sub(r"\r\n?", "\n", text)).strip()


def _plain_text_sections(text: str) -> list[ExtractedSection]:
    """Recognize simple Markdown, all-caps, and colon-terminated headings."""
    sections: list[ExtractedSection] = []
    heading: str | None = None
    body: list[str] = []

    def flush() -> None:
        content = _clean_text("\n".join(body))
        if content:
            sections.append(ExtractedSection(heading, content, {}))

    for raw_line in text.splitlines():
        line = raw_line.strip()
        is_heading = bool(
            line
            and len(line) <= 100
            and (
                line.startswith("#")
                or line.endswith(":")
                or (line.isupper() and any(char.isalpha() for char in line))
            )
        )
        if is_heading:
            flush()
            heading = line.lstrip("# ").rstrip(":").strip() or None
            body = []
        else:
            body.append(raw_line)
    flush()
    if sections:
        return sections
    cleaned = _clean_text(text)
    return [ExtractedSection(None, cleaned, {})] if cleaned else []


def extract_document(path: str | Path) -> list[ExtractedSection]:
    """Extract text-layer content; OCR is deliberately out of scope."""
    file_path = Path(path)
    extension = file_path.suffix.lower()
    if extension not in SUPPORTED_EXTENSIONS:
        raise UnsupportedDocumentError(f"Unsupported document format: {extension}")
    try:
        if extension == ".txt":
            return _plain_text_sections(file_path.read_text(encoding="utf-8"))
        if extension == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            sections = []
            for page_number, page in enumerate(reader.pages, start=1):
                content = _clean_text(page.extract_text() or "")
                if content:
                    sections.append(
                        ExtractedSection(
                            f"Page {page_number}", content, {"page": page_number}
                        )
                    )
            return sections

        from docx import Document

        document = Document(str(file_path))
        sections: list[ExtractedSection] = []
        heading: str | None = None
        paragraphs: list[str] = []

        def flush_docx() -> None:
            content = _clean_text("\n".join(paragraphs))
            if content:
                sections.append(ExtractedSection(heading, content, {}))

        for paragraph in document.paragraphs:
            value = paragraph.text.strip()
            if not value:
                continue
            if paragraph.style and paragraph.style.name.lower().startswith("heading"):
                flush_docx()
                heading = value
                paragraphs = []
            else:
                paragraphs.append(value)
        flush_docx()
        return sections
    except UnsupportedDocumentError:
        raise
    except Exception as error:
        raise DocumentIngestionError(
            f"Could not extract {extension or 'document'} content"
        ) from error


def chunk_sections(
    sections: list[ExtractedSection],
    *,
    max_words: int = 180,
    overlap_words: int = 30,
) -> list[ExtractedSection]:
    if max_words <= 0 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("chunk sizes must satisfy 0 <= overlap < max_words")
    chunks: list[ExtractedSection] = []
    step = max_words - overlap_words
    for section in sections:
        words = section.content.split()
        for start in range(0, len(words), step):
            content = " ".join(words[start : start + max_words]).strip()
            if not content:
                continue
            metadata = dict(section.metadata)
            metadata["word_start"] = start
            chunks.append(ExtractedSection(section.title, content, metadata))
            if start + max_words >= len(words):
                break
    return chunks


class DocumentIngestor:
    """Extract, chunk, normalize, and durably replace one source's chunks."""

    def __init__(
        self,
        repository: KnowledgeChunkRepository,
        *,
        max_words: int = 180,
        overlap_words: int = 30,
    ) -> None:
        self.repository = repository
        self.max_words = max_words
        self.overlap_words = overlap_words

    def ingest_file(
        self,
        path: str | Path,
        *,
        document_type: KnowledgeDocumentType,
        source_document_id: str | None = None,
        source_title: str | None = None,
    ) -> IngestionResult:
        file_path = Path(path)
        if not file_path.is_file():
            raise DocumentIngestionError("Document path is not a file")
        raw_bytes = file_path.read_bytes()
        content_hash = sha256(raw_bytes).hexdigest()
        title = source_title or file_path.stem
        source_id = source_document_id or (
            "doc-" + sha256(f"{document_type}:{title.lower()}".encode()).hexdigest()[:24]
        )
        sections = extract_document(file_path)
        if not sections:
            raise DocumentIngestionError("Document contains no extractable text layer")
        pieces = chunk_sections(
            sections, max_words=self.max_words, overlap_words=self.overlap_words
        )
        chunks: list[KnowledgeChunk] = []
        for index, piece in enumerate(pieces):
            normalized = preprocess_for_retrieval(piece.content)
            if not normalized:
                continue
            chunk_id = "chk-" + sha256(
                f"{source_id}:{index}:{piece.content}".encode()
            ).hexdigest()[:32]
            metadata = {
                **piece.metadata,
                "chunk_index": index,
                "content_hash": content_hash,
                "source_extension": file_path.suffix.lower(),
            }
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    source_document_id=source_id,
                    source_title=title,
                    document_type=document_type,
                    section=piece.title,
                    content=piece.content,
                    normalized_content=normalized,
                    metadata=metadata,
                )
            )
        if not chunks:
            raise DocumentIngestionError("Document produced no searchable chunks")
        existing = self.repository.get_knowledge_chunks_by_source(source_id)
        if existing and all(
            item.metadata.get("content_hash") == content_hash for item in existing
        ):
            return IngestionResult(source_id, title, 0, True)
        stored = self.repository.replace_knowledge_chunks(source_id, chunks)
        return IngestionResult(source_id, title, len(stored), False)
