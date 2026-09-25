from __future__ import annotations
from backend.app.security.input_sanitization import sanitize_user_text, InputSanitizationError
"""Controlled TXT/PDF/DOCX ingestion for the classical IR corpus."""


from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
import re
from typing import Protocol

from backend.app.retrieval.preprocessing import preprocess_for_retrieval
from backend.app.retrieval.schemas import KnowledgeChunk, KnowledgeDocumentType
from backend.app.policy_types import normalize_policy_type


SUPPORTED_EXTENSIONS = frozenset({".txt", ".pdf", ".docx"})
INGESTION_PIPELINE_VERSION = "section-aware-v2"
_NUMBERED_SECTION = re.compile(
    r"^(?:section|part|chapter)\s+[0-9]+[a-z]?\s*[:.\-]\s*\S.+$",
    re.IGNORECASE,
)


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
    if not text:
        return ""
    try:
        sanitized = sanitize_user_text(text)
    except Exception:
        sanitized = text.replace("\x00", "")
    return re.sub(r"[ \t]+", " ", re.sub(r"\r\n?", "\n", sanitized)).strip()


def _plain_text_sections(text: str) -> list[ExtractedSection]:
    """Extract headings without mistaking prose/list introductions for headings."""
    sections: list[ExtractedSection] = []
    heading: str | None = None
    body: list[str] = []
    preamble: str | None = None
    preamble_attached = False

    def flush() -> None:
        nonlocal preamble_attached
        content = _clean_text("\n".join(body))
        if content:
            metadata: dict[str, object] = {}
            if preamble and not preamble_attached:
                metadata["document_preamble"] = preamble
                preamble_attached = True
            sections.append(ExtractedSection(heading, content, metadata))

    def is_heading(line: str) -> bool:
        if not line or len(line) > 120:
            return False
        if line.startswith("#") or _NUMBERED_SECTION.fullmatch(line):
            return True
        letters = [character for character in line if character.isalpha()]
        return bool(letters and line.rstrip(":").isupper())

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if is_heading(line):
            if heading is None and not sections:
                leading_text = _clean_text("\n".join(body))
                if leading_text:
                    preamble = leading_text
            else:
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
            style_name = paragraph.style.name.lower() if paragraph.style else ""
            if style_name.startswith("heading"):
                flush_docx()
                heading = value
                paragraphs = []
            else:
                if style_name.startswith("list bullet"):
                    value = f"- {value}"
                elif style_name.startswith("list number"):
                    value = f"1. {value}"
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
    """Create section-aware chunks while retaining line and list formatting."""
    if max_words <= 0 or overlap_words < 0 or overlap_words >= max_words:
        raise ValueError("chunk sizes must satisfy 0 <= overlap < max_words")
    chunks: list[ExtractedSection] = []

    def word_count(value: str) -> int:
        return len(value.split())

    def split_long_line(line: str, limit: int) -> list[str]:
        words = line.split()
        if len(words) <= limit:
            return [line]
        marker = ""
        if words and words[0] in {"-", "*", "•"}:
            marker = words.pop(0) + " "
        width = max(1, limit - (1 if marker else 0))
        return [
            marker + " ".join(words[index : index + width])
            for index in range(0, len(words), width)
        ]

    for section in sections:
        preamble = str(section.metadata.get("document_preamble") or "").strip()
        first_prefix = [value for value in (preamble, section.title) if value]
        continuation_prefix = [section.title] if section.title else []
        prefix_budget = max(
            word_count("\n".join(first_prefix)),
            word_count("\n".join(continuation_prefix)),
        )
        body_limit = max(1, max_words - prefix_budget)
        lines: list[str] = []
        for line in section.content.splitlines():
            if not line.strip():
                lines.append("")
            else:
                lines.extend(split_long_line(line.strip(), body_limit))

        groups: list[tuple[list[str], int]] = []
        current: list[str] = []
        current_words = 0
        index = 0
        while index < len(lines):
            line = lines[index]
            count = word_count(line)
            if current and count and current_words + count > body_limit:
                groups.append((current, current_words))
                overlap: list[str] = []
                overlap_count = 0
                for previous in reversed(current):
                    previous_count = word_count(previous)
                    if previous_count and overlap_count + previous_count > overlap_words:
                        break
                    overlap.insert(0, previous)
                    overlap_count += previous_count
                current = overlap
                current_words = overlap_count
                while current and current_words + count > body_limit:
                    removed = current.pop(0)
                    current_words -= word_count(removed)
                continue
            current.append(line)
            current_words += count
            index += 1
        if current and any(value.strip() for value in current):
            groups.append((current, current_words))

        unique_word_start = 0
        for group_index, (body_lines, _) in enumerate(groups):
            prefix = first_prefix if group_index == 0 else continuation_prefix
            content = _clean_text("\n".join([*prefix, *body_lines]))
            metadata = dict(section.metadata)
            metadata.pop("document_preamble", None)
            metadata["word_start"] = unique_word_start
            chunks.append(ExtractedSection(section.title, content, metadata))
            unique_word_start += max(0, word_count("\n".join(body_lines)) - overlap_words)
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
        policy_type: str | None = None,
        metadata: dict[str, object] | None = None,
    ) -> IngestionResult:
        file_path = Path(path)
        if not file_path.is_file():
            raise DocumentIngestionError("Document path is not a file")
        raw_bytes = file_path.read_bytes()
        content_hash = sha256(raw_bytes).hexdigest()
        title = source_title or file_path.stem
        inferred_policy_type = normalize_policy_type(policy_type)
        if not inferred_policy_type:
            lowered_stem = file_path.stem.lower()
            if "full_comprehensive" in lowered_stem:
                inferred_policy_type = "full_comprehensive"
            elif "partial_comprehensive" in lowered_stem:
                inferred_policy_type = "partial_comprehensive"
            elif "third_party" in lowered_stem:
                inferred_policy_type = "third_party"

        source_id = source_document_id or (
            "doc-" + sha256(f"{document_type}:{title.lower()}:{inferred_policy_type or ''}".encode()).hexdigest()[:24]
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
            chunk_meta = {
                **piece.metadata,
                **(metadata or {}),
                "chunk_index": index,
                "content_hash": content_hash,
                "ingestion_pipeline_version": INGESTION_PIPELINE_VERSION,
                "source_extension": file_path.suffix.lower(),
            }
            if inferred_policy_type:
                chunk_meta["policy_type"] = inferred_policy_type
            chunk_meta.setdefault("status", "active")
            chunk_meta.setdefault("audience", "customer")
            chunks.append(
                KnowledgeChunk(
                    chunk_id=chunk_id,
                    source_document_id=source_id,
                    source_title=title,
                    document_type=document_type,
                    section=piece.title,
                    content=piece.content,
                    normalized_content=normalized,
                    metadata=chunk_meta,
                )
            )
        if not chunks:
            raise DocumentIngestionError("Document produced no searchable chunks")
        existing = self.repository.get_knowledge_chunks_by_source(source_id)
        if (
            existing
            and {item.chunk_id for item in existing}
            == {item.chunk_id for item in chunks}
            and all(
                item.metadata.get("content_hash") == content_hash
                and item.metadata.get("ingestion_pipeline_version")
                == INGESTION_PIPELINE_VERSION
                for item in existing
            )
        ):
            return IngestionResult(source_id, title, 0, True)
        stored = self.repository.replace_knowledge_chunks(source_id, chunks)
        return IngestionResult(source_id, title, len(stored), False)
