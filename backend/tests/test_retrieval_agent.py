from backend.app.retrieval.schemas import (
    RetrievalRequest,
    UserContext,
    IntentContext,
    ClaimContext,
    PolicyLookupContext,
    ClaimLookupContext,
    DocumentReference,
)

from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever


class FakeRetrievalRepository:
    def get_policy_by_number(self, policy_number, user_id):
        if (
            policy_number == "MTR-10023"
            and user_id == "USER001"
        ):
            return {
                "id": "POL001",
                "policy_number": "MTR-10023",
                "customer_id": "USER001",
                "status": "active",
                "start_date": "2026-08-01",
                "end_date": "2027-08-01",
                "coverage_details": {
                    "collision": True,
                    "theft": True,
                },
            }

        return None

    def get_policy_by_id(self, policy_id, user_id):
        if (
            policy_id == "POL001"
            and user_id == "USER001"
        ):
            return {
                "id": "POL001",
                "policy_number": "MTR-10023",
                "customer_id": "USER001",
                "status": "active",
                "start_date": "2026-08-01",
                "end_date": "2027-08-01",
                "coverage_details": {
                    "collision": True,
                    "theft": True,
                },
            }

        return None

    def get_claim_by_id(self, claim_id, user_id):
        if (
            claim_id == "CLM001"
            and user_id == "USER001"
        ):
            return {
                "id": "CLM001",
                "claim_reference": "CLM-2026-001",
                "customer_id": "USER001",
                "policy_id": "POL001",
                "claim_type": "vehicle_collision",
                "incident_date": "2026-09-16",
                "incident_location": "Kandy",
                "claimed_amount": 150000.00,
                "status": "under_review",
            }

        return None

    def get_claim_by_reference(
        self,
        claim_reference,
        user_id,
    ):
        if (
            claim_reference == "CLM-2026-001"
            and user_id == "USER001"
        ):
            return self.get_claim_by_id(
                "CLM001",
                user_id,
            )

        return None

    def get_policy_claim_history(
        self,
        policy_id: str,
        user_id: str,
        exclude_claim_id: str | None = None,
    ) -> list[dict]:

        if (
            policy_id == "POL001"
            and user_id == "USER001"
        ):
            return [
                {
                    "id": "CLM000",
                    "claim_reference": "CLM-2026-000",
                    "claim_type": "windscreen_damage",
                    "incident_date": "2026-05-10",
                    "claimed_amount": 50000.00,
                    "status": "approved",
                }
            ]

        return []

    def get_claim_documents(
        self,
        claim_id: str,
        user_id: str,
    ) -> list[dict]:

        if (
            claim_id == "CLM001"
            and user_id == "USER001"
        ):
            return [
                {
                    "id": "DOC001",
                    "document_type": "police_report",
                    "file_name": "police_report.pdf",
                    "incident_date": "2026-09-16",
                    "claim_amount": None,
                    "incident_type": "vehicle_collision",
                    "police_report_number": "PR-1001",
                    "extracted_text": "Accident reported in Kandy.",
                }
            ]

        return []


class FakeKnowledgeRetriever:
    def retrieve(
        self,
        query: str,
        insurance_type: str = "motor",
        top_k: int = 3,
        min_relevance_score: float = 0.7,
    ) -> list:
        # Return empty list for knowledge retrieval in these tests
        # Focus is on testing structured retrieval
        return []


def test_claim_submission_success():
    repository = FakeRetrievalRepository()
    knowledge_retriever = FakeKnowledgeRetriever()

    service = RetrievalService(
        repository=repository,
        knowledge_retriever=knowledge_retriever
    )

    request = RetrievalRequest(
        request_id="REQ001",
        user_context=UserContext(
            user_id="USER001"
        ),
        intent_context=IntentContext(
            intent="claim_submission",
            confidence=0.95,
        ),
        policy_context=PolicyLookupContext(
            policy_number="MTR-10023"
        ),
    )

    response = service.retrieve(request)

    assert response.status == "success"

    assert response.result.policy_data is not None

    assert (
        response.result.policy_data.policy_number
        == "MTR-10023"
    )

    assert len(
        response.result.historical_claims
    ) == 1


def test_claim_submission_policy_not_found():
    repository = FakeRetrievalRepository()
    knowledge_retriever = FakeKnowledgeRetriever()

    service = RetrievalService(
        repository=repository,
        knowledge_retriever=knowledge_retriever
    )

    request = RetrievalRequest(
        request_id="REQ002",
        user_context=UserContext(
            user_id="USER001"
        ),
        intent_context=IntentContext(
            intent="claim_submission",
            confidence=0.90,
        ),
        policy_context=PolicyLookupContext(
            policy_number="INVALID"
        ),
    )

    response = service.retrieve(request)

    assert response.status == "no_results"

    assert response.result.policy_data is None

    assert (
        "policy_not_found"
        in response.result.missing_evidence
    )


def test_claim_status_success():
    repository = FakeRetrievalRepository()
    knowledge_retriever = FakeKnowledgeRetriever()

    service = RetrievalService(
        repository=repository,
        knowledge_retriever=knowledge_retriever
    )

    request = RetrievalRequest(
        request_id="REQ003",
        user_context=UserContext(
            user_id="USER001"
        ),
        intent_context=IntentContext(
            intent="claim_status",
            confidence=0.99,
        ),
        claim_lookup=ClaimLookupContext(
            claim_id="CLM001"
        ),
    )

    response = service.retrieve(request)

    assert response.status == "success"

    assert response.result.claim_record is not None

    assert (
        response.result.claim_record.status
        == "under_review"
    )


def test_claim_status_missing_identifier():
    repository = FakeRetrievalRepository()
    knowledge_retriever = FakeKnowledgeRetriever()

    service = RetrievalService(
        repository=repository,
        knowledge_retriever=knowledge_retriever
    )

    request = RetrievalRequest(
        request_id="REQ004",
        user_context=UserContext(
            user_id="USER001"
        ),
        intent_context=IntentContext(
            intent="claim_status",
            confidence=0.95,
        ),
    )

    response = service.retrieve(request)

    assert response.status == "no_results"

    assert (
        "claim_identifier_missing"
        in response.result.missing_evidence
    )


def test_wrong_user_cannot_retrieve_policy():
    repository = FakeRetrievalRepository()
    knowledge_retriever = FakeKnowledgeRetriever()

    service = RetrievalService(
        repository=repository,
        knowledge_retriever=knowledge_retriever
    )

    request = RetrievalRequest(
        request_id="REQ005",
        user_context=UserContext(
            user_id="USER999"
        ),
        intent_context=IntentContext(
            intent="coverage_question",
            confidence=0.95,
        ),
        policy_context=PolicyLookupContext(
            policy_number="MTR-10023"
        ),
    )

    response = service.retrieve(request)

    assert response.status == "no_results"

    assert response.result.policy_data is None
