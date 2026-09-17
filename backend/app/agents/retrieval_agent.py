from app.retrieval.schemas import (
    RetrievalRequest,
    UserContext,
    IntentContext,
    ClaimContext,
    PolicyLookupContext,
    ClaimLookupContext,
    DocumentReference,
)

from app.retrieval.service import RetrievalService
from app.retrieval.repository import RetrievalRepository
from app.retrieval.knowledge_retriever import KnowledgeRetriever

from app.services.supabase_service import get_supabase_client


def retrieval_agent(state: dict) -> dict:
    """
    LangGraph node for retrieval.

    Reads structured state,
    performs authorized retrieval,
    and returns retrieval results
    back into the shared graph state.
    """

    supabase_client = get_supabase_client()

    repository = RetrievalRepository(
        client=supabase_client
    )

    knowledge_retriever = KnowledgeRetriever(
        client=supabase_client
    )

    service = RetrievalService(
        repository=repository,
        knowledge_retriever=knowledge_retriever,
    )

    request = RetrievalRequest(
        request_id=state["request_id"],

        user_context=UserContext(
            user_id=state["user_id"]
        ),

        intent_context=IntentContext(
            intent=state["intent"],
            confidence=state.get(
                "intent_confidence"
            ),
        ),

        claim_context=(
            ClaimContext(
                incident_type=state.get(
                    "incident_type"
                ),
                incident_date=state.get(
                    "incident_date"
                ),
                incident_location=state.get(
                    "incident_location"
                ),
                damage_areas=state.get(
                    "damage_areas",
                    [],
                ),
            )
            if state.get("claim_context") is not None
            or state.get("incident_type") is not None
            else None
        ),

        policy_context=(
            PolicyLookupContext(
                policy_id=state.get(
                    "policy_id"
                ),
                policy_number=state.get(
                    "policy_number"
                ),
            )
            if (
                state.get("policy_id")
                or state.get("policy_number")
            )
            else None
        ),

        claim_lookup=(
            ClaimLookupContext(
                claim_id=state.get(
                    "claim_id"
                ),
                claim_reference=state.get(
                    "claim_reference"
                ),
            )
            if (
                state.get("claim_id")
                or state.get("claim_reference")
            )
            else None
        ),

        document_references=[
            DocumentReference(**doc)
            for doc in state.get(
                "document_references",
                [],
            )
        ],
    )

    response = service.retrieve(request)

    return {
        "retrieval_response": response.model_dump(
            mode="json"
        ),
        "retrieval_status": response.status,
    }