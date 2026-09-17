"""Canonical Supabase adapter for retrieval data."""

from __future__ import annotations

from typing import Any
from supabase import Client

from backend.app.retrieval.schemas import (
    ClaimRecord,
    DocumentEvidence,
    HistoricalClaim,
    KnowledgeChunk,
    KnowledgeDocumentType,
    PolicyRecord,
)


class RetrievalRepository:
    """Translate canonical database rows into retrieval contracts."""

    def __init__(self, client: Client):
        self.client = client

    @staticmethod
    def policy_from_row(row: dict[str, Any]) -> PolicyRecord:
        return PolicyRecord(
            policy_id=row["policy_id"], policy_number=row["policy_number"],
            customer_id=row["customer_id"], status=row["status"],
            start_date=str(row["start_date"]), end_date=str(row["end_date"]),
            coverage_details=row.get("coverage_details") or {},
        )

    @staticmethod
    def claim_from_row(row: dict[str, Any]) -> ClaimRecord:
        return ClaimRecord(
            claim_id=row["claim_id"], claim_reference=row["claim_reference"],
            customer_id=row["customer_id"], policy_id=row["policy_id"],
            claim_type=row["incident_type"], incident_date=str(row["incident_date"]),
            incident_location=row.get("incident_location"),
            claimed_amount=row.get("claimed_amount"), status=row.get("claim_status"),
        )

    @staticmethod
    def history_from_row(row: dict[str, Any]) -> HistoricalClaim:
        return HistoricalClaim(
            claim_id=row["claim_id"], claim_reference=row["claim_reference"],
            claim_type=row["incident_type"], incident_date=str(row["incident_date"]),
            claimed_amount=row.get("claimed_amount"), status=row.get("claim_status"),
            police_report_number=row.get("police_report_number"),
        )

    @staticmethod
    def document_from_row(row: dict[str, Any]) -> DocumentEvidence:
        return DocumentEvidence(
            document_id=row["document_id"], document_type=row["document_type"],
            file_name=row.get("file_name"),
            incident_date=str(row["incident_date"]) if row.get("incident_date") else None,
            claim_amount=row.get("claim_amount"), incident_type=row.get("incident_type"),
            police_report_number=row.get("police_report_number"),
            extracted_text=row.get("extracted_text"),
        )

    @staticmethod
    def knowledge_chunk_from_row(row: dict[str, Any]) -> KnowledgeChunk:
        return KnowledgeChunk.model_validate(row)

    def get_policy_by_number(self, policy_number: str, user_id: str) -> PolicyRecord | None:
        response = (self.client.table("policies").select("*")
                    .eq("policy_number", policy_number).eq("customer_id", user_id)
                    .limit(1).execute())
        return self.policy_from_row(response.data[0]) if response.data else None

    def get_policy_by_id(self, policy_id: str, user_id: str) -> PolicyRecord | None:
        response = (self.client.table("policies").select("*")
                    .eq("policy_id", policy_id).eq("customer_id", user_id)
                    .limit(1).execute())
        return self.policy_from_row(response.data[0]) if response.data else None

    def get_claim_by_id(self, claim_id: str, user_id: str) -> ClaimRecord | None:
        response = (self.client.table("claims").select("*")
                    .eq("claim_id", claim_id).eq("customer_id", user_id)
                    .limit(1).execute())
        return self.claim_from_row(response.data[0]) if response.data else None

    def get_claim_by_reference(self, claim_reference: str, user_id: str) -> ClaimRecord | None:
        response = (self.client.table("claims").select("*")
                    .eq("claim_reference", claim_reference).eq("customer_id", user_id)
                    .limit(1).execute())
        return self.claim_from_row(response.data[0]) if response.data else None

    def get_policy_claim_history(
        self, policy_id: str, user_id: str, exclude_claim_id: str | None = None,
    ) -> list[HistoricalClaim]:
        query = (self.client.table("claims")
                 .select("claim_id,claim_reference,incident_type,incident_date,claimed_amount,claim_status,police_report_number")
                 .eq("policy_id", policy_id).eq("customer_id", user_id))
        if exclude_claim_id:
            query = query.neq("claim_id", exclude_claim_id)
        response = query.execute()
        return [self.history_from_row(row) for row in (response.data or [])]

    def get_claim_documents(self, claim_id: str, user_id: str) -> list[DocumentEvidence]:
        response = (self.client.table("claim_documents").select("*")
                    .eq("claim_id", claim_id).eq("customer_id", user_id).execute())
        return [self.document_from_row(row) for row in (response.data or [])]

    def list_knowledge_chunks(
        self,
        *,
        insurance_type: str = "motor",
        document_type: KnowledgeDocumentType | None = None,
    ) -> list[KnowledgeChunk]:
        query = (self.client.table("knowledge_chunks").select("*")
                 .eq("insurance_type", insurance_type))
        if document_type is not None:
            query = query.eq("document_type", document_type)
        response = query.execute()
        return [self.knowledge_chunk_from_row(row) for row in (response.data or [])]

    def get_knowledge_chunks_by_source(
        self, source_document_id: str
    ) -> list[KnowledgeChunk]:
        response = (self.client.table("knowledge_chunks").select("*")
                    .eq("source_document_id", source_document_id).execute())
        return [self.knowledge_chunk_from_row(row) for row in (response.data or [])]

    def upsert_knowledge_chunks(
        self, chunks: list[KnowledgeChunk]
    ) -> list[KnowledgeChunk]:
        if not chunks:
            return []
        rows = [
            item.model_dump(mode="json", exclude_none=True) for item in chunks
        ]
        response = (self.client.table("knowledge_chunks")
                    .upsert(rows, on_conflict="chunk_id").execute())
        returned = response.data or rows
        return [self.knowledge_chunk_from_row(row) for row in returned]

    def replace_knowledge_chunks(
        self,
        source_document_id: str,
        chunks: list[KnowledgeChunk],
    ) -> list[KnowledgeChunk]:
        """Upsert a source, then remove only that source's stale chunk IDs."""
        if any(item.source_document_id != source_document_id for item in chunks):
            raise ValueError("All chunks must belong to the requested source")
        if not chunks:
            self.delete_knowledge_chunks_for_source(source_document_id)
            return []
        existing = self.get_knowledge_chunks_by_source(source_document_id)
        stored = self.upsert_knowledge_chunks(chunks)
        current_ids = {item.chunk_id for item in chunks}
        stale_ids = [item.chunk_id for item in existing if item.chunk_id not in current_ids]
        if stale_ids:
            (self.client.table("knowledge_chunks").delete()
             .eq("source_document_id", source_document_id)
             .in_("chunk_id", stale_ids).execute())
        return stored

    def delete_knowledge_chunks_for_source(
        self, source_document_id: str
    ) -> None:
        """Delete exactly one explicitly selected source, never the whole corpus."""
        (self.client.table("knowledge_chunks").delete()
         .eq("source_document_id", source_document_id).execute())
