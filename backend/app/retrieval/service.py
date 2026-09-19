import logging
from typing import Optional

from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.schemas import (
    RetrievalRequest,
    RetrievalResponse,
    RetrievalResult,
    PolicyRecord,
    ClaimRecord,
    HistoricalClaim,
    DocumentEvidence,
    KnowledgeEvidence,
    RetrievalError,
)
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.schemas.domain import EvidenceItem


logger = logging.getLogger(__name__)


class RetrievalService:
    def __init__(
        self,
        repository: RetrievalRepository,
        knowledge_retriever: Optional[KnowledgeRetriever] = None,
    ):
        self.repository = repository
        self.knowledge_retriever = knowledge_retriever

    def retrieve(
        self,
        request: RetrievalRequest,
    ) -> RetrievalResponse:

        intent = request.intent_context.intent
        user_id = request.user_context.user_id
        try:
            if intent == "claim_submission":
                result = self._handle_claim_submission(request, user_id)
            elif intent == "claim_status":
                result = self._handle_claim_status(request, user_id)
            elif intent in {"policy_question", "coverage_question"}:
                result = self._handle_policy_retrieval(request, user_id)
            elif intent in {"required_documents_question", "general_information"}:
                result = self._handle_knowledge_retrieval(request, user_id)
            else:
                result = RetrievalResult(
                    missing_evidence=["unsupported_retrieval_intent"]
                )
            status = self._determine_status(
                result, intent=intent, errors=result.component_errors
            )
            return RetrievalResponse(
                request_id=request.request_id,
                status=status,
                result=result,
                errors=result.component_errors,
            )
        except Exception:
            logger.exception("Retrieval operation failed")
            return RetrievalResponse(
                request_id=request.request_id,
                status="failed",
                result=RetrievalResult(),
                errors=[RetrievalError(
                    error_code="retrieval_failed",
                    message="Retrieval could not be completed safely.",
                    source="retrieval_service",
                    retryable=True,
                )],
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
        else:
            result.policy_data = self._coerce_policy(policy)

            claim_id = (
                request.claim_lookup.claim_id
                if request.claim_lookup is not None
                else None
            )
            if claim_id:
                claim_record = self.repository.get_claim_by_id(
                    claim_id=claim_id,
                    user_id=user_id,
                )
                if claim_record is not None:
                    result.claim_record = self._coerce_claim(claim_record)

            claim_history = self.repository.get_policy_claim_history(
                policy_id=result.policy_data.policy_id,
                user_id=user_id,
                exclude_claim_id=claim_id,
            )

            result.historical_claims = [
                row if isinstance(row, HistoricalClaim) else HistoricalClaim(
                    claim_id=row.get("claim_id", row.get("id")),
                    claim_reference=row["claim_reference"],
                    claim_type=row.get("incident_type", row.get("claim_type")),
                    incident_date=str(row["incident_date"]),
                    claimed_amount=row.get("claimed_amount"),
                    status=row.get("claim_status", row.get("status")),
                    police_report_number=row.get("police_report_number"),
                )
                for row in claim_history
            ]

            if request.claim_lookup:
                if claim_id:
                    documents = (
                        self.repository.get_claim_documents(
                            claim_id=claim_id,
                            user_id=user_id,
                        )
                    )

                    result.document_facts = [
                        row if isinstance(row, DocumentEvidence) else DocumentEvidence(
                            document_id=row.get("document_id", row.get("id")),
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

        # Add optional knowledge retrieval for claim_submission
        # For example, get relevant claim processing knowledge
        if self.knowledge_retriever:
            knowledge_query = self._build_claim_submission_knowledge_query(request)
            if knowledge_query:
                self._search_knowledge(result, knowledge_query, top_k=3)

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

        result.claim_record = self._coerce_claim(claim)

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
        if policy is not None:
            result.policy_data = self._coerce_policy(policy)
        elif request.policy_context is not None:
            result.missing_evidence.append("policy_not_found")
        elif request.query and "my policy" in request.query.lower():
            result.missing_evidence.append("specific_policy_not_available")
            result.warnings.append(
                "Knowledge evidence is generic and is not confirmation of this customer's policy."
            )

        # Add policy knowledge for policy_question and coverage_question
        if self.knowledge_retriever:
            knowledge_query = self._build_policy_knowledge_query(request)
            if knowledge_query:
                self._search_knowledge(result, knowledge_query, top_k=3)

        if not result.policy_data and not result.knowledge_evidence:
            if "knowledge_evidence_not_found" not in result.missing_evidence:
                result.missing_evidence.append("knowledge_evidence_not_found")

        return result

    def _handle_knowledge_retrieval(
        self,
        request: RetrievalRequest,
        user_id: str,
    ) -> RetrievalResult:

        result = RetrievalResult()

        if self.knowledge_retriever:
            # Handle required_documents_question and general_information with knowledge retrieval
            knowledge_query = self._build_general_knowledge_query(request)
            if knowledge_query:
                self._search_knowledge(result, knowledge_query, top_k=5)

            # If no specific knowledge query could be built, add a warning
            if not knowledge_query and not result.knowledge_evidence:
                result.warnings.append(
                    "Knowledge retrieval query could not be constructed from request"
                )
        else:
            result.warnings.append(
                "Knowledge retrieval is unavailable for this service instance."
            )

        if not result.knowledge_evidence:
            result.missing_evidence.append("knowledge_evidence_not_found")

        return result

    def _retrieve_policy(
        self,
        request: RetrievalRequest,
        user_id: str,
    ) -> PolicyRecord | None:

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

    @staticmethod
    def _coerce_policy(policy) -> PolicyRecord:
        """Keep test doubles compatible while production repositories return models."""
        if isinstance(policy, PolicyRecord):
            return policy
        return PolicyRecord(
            policy_id=policy.get("policy_id", policy.get("id")),
            policy_number=policy["policy_number"],
            customer_id=policy["customer_id"],
            status=policy["status"],
            start_date=str(policy["start_date"]),
            end_date=str(policy["end_date"]),
            coverage_details=policy.get("coverage_details", {}),
        )

    @staticmethod
    def _coerce_claim(claim) -> ClaimRecord:
        if isinstance(claim, ClaimRecord):
            return claim
        return ClaimRecord(
            claim_id=claim.get("claim_id", claim.get("id")),
            claim_reference=claim["claim_reference"],
            customer_id=claim["customer_id"],
            policy_id=claim["policy_id"],
            claim_type=claim.get("incident_type", claim.get("claim_type")),
            incident_date=str(claim["incident_date"]),
            incident_location=claim.get("incident_location"),
            claimed_amount=claim.get("claimed_amount"),
            status=claim.get("claim_status", claim.get("status")),
        )

    def _build_claim_submission_knowledge_query(self, request: RetrievalRequest) -> Optional[str]:
        """Build a knowledge query for claim_submission intent focusing on required supporting documents."""
        parts = []

        if request.claim_context and request.claim_context.incident_type:
            incident_type_str = request.claim_context.incident_type.replace("_", " ")
            parts.append(f"required documents supporting documents for {incident_type_str} claim")
        elif request.query:
            parts.append(f"required documents supporting documents {request.query}")
        else:
            parts.append("required documents supporting documents motor insurance claim")

        return " ".join(parts)

    def _build_policy_knowledge_query(self, request: RetrievalRequest) -> Optional[str]:
        """Build a knowledge query for policy-related intents."""
        if request.query:
            return request.query
        parts = []

        # Add specific policy details if available
        if request.policy_context:
            if request.policy_context.policy_number:
                parts.append(f"policy {request.policy_context.policy_number}")

        # Add intent-specific context
        if request.intent_context.intent == "coverage_question":
            if request.claim_context and request.claim_context.incident_type:
                parts.append(f"coverage for {request.claim_context.incident_type.replace('_', ' ')}")
            else:
                parts.append("motor insurance coverage details")
        elif request.intent_context.intent == "policy_question":
            parts.append("motor insurance policy information")

        if parts:
            return " ".join(parts)
        return None

    def _build_general_knowledge_query(self, request: RetrievalRequest) -> Optional[str]:
        """Build a knowledge query for general information intents."""
        if request.query:
            return request.query
        parts = []

        # Add context from the request
        if request.claim_context:
            if request.claim_context.incident_type:
                parts.append(request.claim_context.incident_type.replace("_", " "))
            if request.claim_context.incident_location:
                parts.append(request.claim_context.incident_location)
            if request.claim_context.damage_areas:
                parts.extend(request.claim_context.damage_areas)

        # Add intent-specific context
        intent = request.intent_context.intent
        if intent == "required_documents_question":
            if request.claim_context and request.claim_context.incident_type:
                parts.append(f"required documents for {request.claim_context.incident_type.replace('_', ' ')} claim")
            else:
                parts.append("required documents for insurance claims")
        elif intent == "general_information":
            parts.append("general motor insurance information")
            if request.claim_context:
                if request.claim_context.incident_type:
                    parts.append(f"about {request.claim_context.incident_type.replace('_', ' ')}")
                if request.claim_context.incident_location:
                    parts.append(f"in {request.claim_context.incident_location}")

        if parts:
            return " ".join(parts)
        return None

    def _determine_status(
        self,
        result: RetrievalResult,
        *,
        intent: str,
        errors: list[RetrievalError],
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

        if errors:
            return "partial_success" if has_data else "failed"
        if has_data and result.missing_evidence:
            return "partial_success"

        if has_data:
            return "success"

        if result.missing_evidence:
            return "no_results"
        if intent in {
            "policy_question",
            "coverage_question",
            "required_documents_question",
            "general_information",
        }:
            return "no_results"
        return "success" if has_data else "no_results"

    def _search_knowledge(
        self,
        result: RetrievalResult,
        query: str,
        *,
        top_k: int,
    ) -> None:
        assert self.knowledge_retriever is not None
        try:
            evidence = self.knowledge_retriever.retrieve(
                query=query,
                insurance_type="motor",
                top_k=top_k,
            )
            self._append_knowledge(result, evidence)
        except Exception:
            logger.exception("Knowledge retrieval component failed")
            result.missing_evidence.append("knowledge_retrieval_failed")
            result.component_errors.append(
                RetrievalError(
                    error_code="knowledge_retrieval_failed",
                    message="Policy knowledge could not be retrieved safely.",
                    source="knowledge_retriever",
                    retryable=True,
                )
            )

    @staticmethod
    def _append_knowledge(
        result: RetrievalResult,
        evidence: list[EvidenceItem] | list[KnowledgeEvidence],
    ) -> None:
        for item in evidence:
            if isinstance(item, KnowledgeEvidence):
                result.knowledge_evidence.append(item)
                continue
            result.knowledge_evidence.append(
                KnowledgeEvidence(
                    evidence_id=item.evidence_id,
                    source_id=str(item.metadata.get("source_document_id", "")),
                    source_title=item.source_title,
                    section=item.section,
                    document_type=item.metadata.get("document_type"),
                    content=item.content,
                    relevance_score=item.score,
                    metadata=dict(item.metadata),
                )
            )
