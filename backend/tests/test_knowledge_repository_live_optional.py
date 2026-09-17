"""Opt-in synthetic knowledge_chunks round trip against development Supabase."""

import os
from uuid import uuid4

import pytest

from backend.app.retrieval.preprocessing import preprocess_for_retrieval
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.schemas import KnowledgeChunk
from backend.app.services.supabase_service import get_supabase_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_KNOWLEDGE_TESTS") != "1",
    reason="Set RUN_SUPABASE_KNOWLEDGE_TESTS=1 for the live corpus round trip",
)


def test_live_synthetic_knowledge_chunk_round_trip():
    repository = RetrievalRepository(get_supabase_client())
    suffix = uuid4().hex
    source_id = f"codex-test-source-{suffix}"
    chunk = KnowledgeChunk(
        chunk_id=f"codex-test-chunk-{suffix}", source_document_id=source_id,
        source_title="Synthetic Test Policy", document_type="policy_manual",
        content="Synthetic windscreen procedure test evidence.",
        normalized_content=preprocess_for_retrieval(
            "Synthetic windscreen procedure test evidence."
        ), metadata={"synthetic_test": True},
    )
    try:
        stored = repository.upsert_knowledge_chunks([chunk])
        assert stored[0].chunk_id == chunk.chunk_id
        assert repository.get_knowledge_chunks_by_source(source_id)[0].content == chunk.content
    finally:
        repository.delete_knowledge_chunks_for_source(source_id)
