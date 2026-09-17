"""Opt-in live Agent 1 -> Orchestrator -> Agent 2 corpus integration."""

import asyncio
import os
from uuid import uuid4

import pytest

from backend.app.orchestrator.agent_clients import (
    LocalClaimIntakeClient,
    LocalRetrievalClient,
)
from backend.app.orchestrator.constants import WorkflowStatus
from backend.app.orchestrator.repository import InMemoryWorkflowRepository
from backend.app.orchestrator.service import OrchestratorService
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.retrieval.preprocessing import preprocess_for_retrieval
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.schemas import KnowledgeChunk
from backend.app.retrieval.service import RetrievalService
from backend.app.schemas.orchestrator import OrchestratorRequest
from backend.app.services.supabase_service import get_supabase_client


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_SUPABASE_ORCHESTRATOR_RETRIEVAL") != "1",
    reason="Set RUN_SUPABASE_ORCHESTRATOR_RETRIEVAL=1 for live Step 4 test",
)


def test_live_orchestrator_retrieves_one_synthetic_chunk():
    repository = RetrievalRepository(get_supabase_client())
    suffix = uuid4().hex
    source_id = f"step4-test-source-{suffix}"
    content = "The other vehicle registration number is a supporting claim document."
    chunk = KnowledgeChunk(
        chunk_id=f"step4-test-chunk-{suffix}",
        source_document_id=source_id,
        source_title="Synthetic Step 4 Guide",
        document_type="procedure_guide",
        section="Vehicle documents",
        content=content,
        normalized_content=preprocess_for_retrieval(content),
        metadata={"synthetic_test": True},
    )
    try:
        repository.upsert_knowledge_chunks([chunk])
        retrieval = KnowledgeRetriever(repository=repository)
        service = OrchestratorService(
            claim_intake_client=LocalClaimIntakeClient(),
            workflow_repository=InMemoryWorkflowRepository(),
            retrieval_client=LocalRetrievalClient(
                RetrievalService(repository, retrieval)
            ),
        )
        response = asyncio.run(service.process_request(
            OrchestratorRequest(
                request_id=f"REQ-{suffix}",
                text="Do you need the other vehicle's registration number",
            ),
            authenticated_user_id=f"synthetic-user-{suffix}",
            authenticated_user_role="customer",
        ))
        assert response.status is WorkflowStatus.RETRIEVAL_COMPLETE
        assert any(
            item["evidence_id"] == chunk.chunk_id
            for item in response.evidence_summary
        )
    finally:
        repository.delete_knowledge_chunks_for_source(source_id)
