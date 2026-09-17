"""Canonical Supabase adapter for retrieval data."""

from __future__ import annotations

from typing import Any
from supabase import Client

from backend.app.retrieval.schemas import (
    ClaimRecord, DocumentEvidence, HistoricalClaim, PolicyRecord,
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
                 .select("claim_id,claim_reference,incident_type,incident_date,claimed_amount,claim_status")
                 .eq("policy_id", policy_id).eq("customer_id", user_id))
        if exclude_claim_id:
            query = query.neq("claim_id", exclude_claim_id)
        response = query.execute()
        return [self.history_from_row(row) for row in (response.data or [])]

    def get_claim_documents(self, claim_id: str, user_id: str) -> list[DocumentEvidence]:
        try:
            response = (self.client.table("claim_documents").select("*")
                        .eq("claim_id", claim_id).eq("customer_id", user_id).execute())
            return [self.document_from_row(row) for row in (response.data or [])]
        except Exception:
            # Documents are supplemental evidence; retain partial-result behavior.
            return []
