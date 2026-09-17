from app.retrieval.repository import RetrievalRepository
from app.retrieval.schemas import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
    PolicyRecord,
    ClaimRecord,
    HistoricalClaim,
    DocumentEvidence,
)


class RetrievalService:
    def __init__(self, repository: RetrievalRepository):
        self.repository = repository

    def retrieve(
        self,
        request: RetrievalRequest,
    ) -> RetrievalResponse:

        intent = request.intent_context.intent
        user_id = request.user_context.user_id

        result = RetrievalResult()

        if intent == "claim_submission":
            result = self._handle_claim_submission(
                request=request,
                user_id=user_id,
            )

        elif intent == "claim_status":
            result = self._handle_claim_status(
                request=request,
                user_id=user_id,
            )

        elif intent in {
            "policy_question",
            "coverage_question",
        }:
            result = self._handle_policy_retrieval(
                request=request,
                user_id=user_id,
            )

        elif intent in {
            "required_documents_question",
            "general_information",
        }:
            result.warnings.append(
                "Knowledge retrieval is not implemented yet."
            )

        else:
            result.warnings.append(
                f"Unsupported retrieval intent: {intent}"
            )

        status = self._determine_status(result)

        return RetrievalResponse(
            request_id=request.request_id,
            status=status,
            result=result,
            errors=[],
        )

    def _handle_claim_submission(
        self,
        request: RetrievalRequest,
        user_id: str,
    ) -> RetrievalResult:

        result = RetrievalResult()

        policy = self._retrieve_policy(
            request=request,
            user_id=user_id,
        )

        if policy is None:
            result.missing_evidence.append(
                "policy_not_found"
            )
            return result

        result.policy_data = PolicyRecord(
            policy_id=policy["id"],
            policy_number=policy["policy_number"],
            customer_id=policy["customer_id"],
            status=policy["status"],
            start_date=str(policy["start_date"]),
            end_date=str(policy["end_date"]),
            coverage_details=policy.get(
                "coverage_details",
                {},
            ),
        )

        claim_history = (
            self.repository.get_policy_claim_history(
                policy_id=policy["id"],
                user_id=user_id,
            )
        )

        result.historical_claims = [
            HistoricalClaim(
                claim_id=row["id"],
                claim_reference=row["claim_reference"],
                claim_type=row["claim_type"],
                incident_date=str(row["incident_date"]),
                claimed_amount=row.get("claimed_amount"),
                status=row.get("status"),
            )
            for row in claim_history
        ]

        if request.claim_lookup:
            claim_id = request.claim_lookup.claim_id

            if claim_id:
                documents = (
                    self.repository.get_claim_documents(
                        claim_id=claim_id,
                        user_id=user_id,
                    )
                )

                result.document_facts = [
                    DocumentEvidence(
                        document_id=row["id"],
                        document_type=row["document_type"],
                        file_name=row.get("file_name"),
                        incident_date=row.get("incident_date"),
                        claim_amount=row.get("claim_amount"),
                        incident_type=row.get("incident_type"),
                        police_report_number=row.get(
                            "police_report_number"
                        ),
                        extracted_text=row.get(
                            "extracted_text"
                        ),
                    )
                    for row in documents
                ]

        return result

    def _handle_claim_status(
        self,
        request: RetrievalRequest,
        user_id: str,
    ) -> RetrievalResult:

        result = RetrievalResult()

        if request.claim_lookup is None:
            result.missing_evidence.append(
                "claim_identifier_missing"
            )
            return result

        claim = None

        if request.claim_lookup.claim_id:
            claim = self.repository.get_claim_by_id(
                claim_id=request.claim_lookup.claim_id,
                user_id=user_id,
            )

        elif request.claim_lookup.claim_reference:
            claim = (
                self.repository.get_claim_by_reference(
                    claim_reference=(
                        request.claim_lookup.claim_reference
                    ),
                    user_id=user_id,
                )
            )

        if claim is None:
            result.missing_evidence.append(
                "claim_not_found"
            )
            return result

        result.claim_record = ClaimRecord(
            claim_id=claim["id"],
            claim_reference=claim["claim_reference"],
            customer_id=claim["customer_id"],
            policy_id=claim["policy_id"],
            claim_type=claim["claim_type"],
            incident_date=str(claim["incident_date"]),
            incident_location=claim.get(
                "incident_location"
            ),
            claimed_amount=claim.get(
                "claimed_amount"
            ),
            status=claim.get("status"),
        )

        return result

    def _handle_policy_retrieval(
        self,
        request: RetrievalRequest,
        user_id: str,
    ) -> RetrievalResult:

        result = RetrievalResult()

        policy = self._retrieve_policy(
            request=request,
            user_id=user_id,
        )

        if policy is None:
            result.missing_evidence.append(
                "policy_not_found"
            )
            return result

        result.policy_data = PolicyRecord(
            policy_id=policy["id"],
            policy_number=policy["policy_number"],
            customer_id=policy["customer_id"],
            status=policy["status"],
            start_date=str(policy["start_date"]),
            end_date=str(policy["end_date"]),
            coverage_details=policy.get(
                "coverage_details",
                {},
            ),
        )

        return result

    def _retrieve_policy(
        self,
        request: RetrievalRequest,
        user_id: str,
    ) -> dict | None:

        if request.policy_context is None:
            return None

        if request.policy_context.policy_id:
            return self.repository.get_policy_by_id(
                policy_id=request.policy_context.policy_id,
                user_id=user_id,
            )

        if request.policy_context.policy_number:
            return self.repository.get_policy_by_number(
                policy_number=(
                    request.policy_context.policy_number
                ),
                user_id=user_id,
            )

        return None

    def _determine_status(
        self,
        result: RetrievalResult,
    ) -> str:

        has_data = any(
            [
                result.policy_data is not None,
                result.claim_record is not None,
                bool(result.historical_claims),
                bool(result.document_facts),
                bool(result.knowledge_evidence),
            ]
        )

        if has_data and result.missing_evidence:
            return "partial_success"

        if has_data:
            return "success"

        if result.missing_evidence:
            return "no_results"

        return "success"