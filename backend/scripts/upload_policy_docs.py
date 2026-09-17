"""Intentionally ingest controlled insurance documents into Supabase.

Run from the repository root, for example:
python -m backend.scripts.upload_policy_docs path/to/docs --document-type policy_manual
"""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.app.retrieval.document_ingestion import (
    DocumentIngestionError,
    DocumentIngestor,
    SUPPORTED_EXTENSIONS,
)
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.schemas import KnowledgeDocumentType
from backend.app.services.supabase_service import get_supabase_client


DOCUMENT_TYPES = list(KnowledgeDocumentType.__args__)


def _files(path: Path) -> tuple[list[Path], list[Path]]:
    candidates = [path] if path.is_file() else sorted(
        item for item in path.rglob("*") if item.is_file()
    )
    supported = [item for item in candidates if item.suffix.lower() in SUPPORTED_EXTENSIONS]
    unsupported = [item for item in candidates if item.suffix.lower() not in SUPPORTED_EXTENSIONS]
    return supported, unsupported


def main() -> int:
    parser = argparse.ArgumentParser(description="Ingest controlled policy documents")
    parser.add_argument("path", type=Path)
    parser.add_argument("--document-type", choices=DOCUMENT_TYPES, required=True)
    args = parser.parse_args()
    if not args.path.exists():
        parser.error("path does not exist")

    repository = RetrievalRepository(get_supabase_client())
    ingestor = DocumentIngestor(repository)
    supported, unsupported = _files(args.path)
    documents_processed = 0
    chunks_written = 0
    duplicates = 0
    failures = 0
    for file_path in supported:
        try:
            result = ingestor.ingest_file(
                file_path, document_type=args.document_type
            )
            documents_processed += 1
            chunks_written += result.chunks_created_or_updated
            duplicates += int(result.duplicate_unchanged)
        except DocumentIngestionError:
            failures += 1
            print(f"FAILED: {file_path.name}")

    print(f"Documents processed: {documents_processed}")
    print(f"Chunks created/updated: {chunks_written}")
    print(f"Unchanged duplicates: {duplicates}")
    print(f"Unsupported files: {len(unsupported)}")
    print(f"Failures: {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
