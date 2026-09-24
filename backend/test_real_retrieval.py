import sys
from pathlib import Path
repo_root = str(Path(__file__).resolve().parent.parent)
backend_dir = str(Path(__file__).resolve().parent)
for p in (repo_root, backend_dir):
    if p not in sys.path:
        sys.path.insert(0, p)

import json
from backend.app.services.supabase_service import get_supabase_client
from backend.app.retrieval.repository import RetrievalRepository
from backend.app.retrieval.schemas import (
    RetrievalRequest,
    UserContext,
    IntentContext,
    PolicyLookupContext,
    ClaimLookupContext,
)
from backend.app.retrieval.service import RetrievalService
from backend.app.retrieval.knowledge_retriever import KnowledgeRetriever
from backend.app.agents.retrieval_agent import retrieval_agent

REAL_POLICY_NUMBER = "MTR-DEMO-1001"
REAL_POLICY_ID = "0023b1f0-ed1e-4c2a-995b-e4070bbef5b1"
REAL_USER_ID = "03f4068e-aa25-467b-8d99-c1fb08fa384f"
WRONG_USER_ID = "00000000-0000-0000-0000-000000000000"
REAL_CLAIM_ID = "a2e22d13-daca-4d64-b7d0-92901b50b5ce"

client = get_supabase_client()
repository = RetrievalRepository(client=client)

if __name__ == "__main__":
    print("=== Step 6: Test a real policy lookup ===")
    policy = repository.get_policy_by_number(
        policy_number=REAL_POLICY_NUMBER,
        user_id=REAL_USER_ID,
    )
    print("POLICY:")
    print(policy)
    assert policy is not None
    assert policy["policy_number"] == REAL_POLICY_NUMBER
    assert policy["customer_id"] == REAL_USER_ID

    print("\n=== Step 7: Test authorization boundary ===")
    policy_unauthorized = repository.get_policy_by_number(
        policy_number=REAL_POLICY_NUMBER,
        user_id=WRONG_USER_ID,
    )
    print("UNAUTHORIZED POLICY RESULT:", policy_unauthorized)
    assert policy_unauthorized is None, "Authorization failed: policy returned for wrong user!"

    print("\n=== Step 8: Test claim retrieval ===")
    claim = repository.get_claim_by_id(
        claim_id=REAL_CLAIM_ID,
        user_id=REAL_USER_ID,
    )
    print("CLAIM:")
    print(claim)
    assert claim is not None
    assert claim["customer_id"] == REAL_USER_ID

    claim_unauthorized = repository.get_claim_by_id(
        claim_id=REAL_CLAIM_ID,
        user_id=WRONG_USER_ID,
    )
    print("UNAUTHORIZED CLAIM RESULT:", claim_unauthorized)
    assert claim_unauthorized is None, "Authorization failed: claim returned for wrong user!"

    print("\n=== Step 9: Test claim history ===")
    history = repository.get_policy_claim_history(
        policy_id=REAL_POLICY_ID,
        user_id=REAL_USER_ID,
    )
    print("HISTORY:")
    print(history)
    assert isinstance(history, list)

    print("\n=== Step 10: Test documents ===")
    documents = repository.get_claim_documents(
        claim_id=REAL_CLAIM_ID,
        user_id=REAL_USER_ID,
    )
    print("DOCUMENTS:")
    print(documents)
    assert isinstance(documents, list)

    print("\n=== Step 11: Test full RetrievalService with real Supabase ===")
    knowledge_retriever = KnowledgeRetriever(client=client)
    service = RetrievalService(
        repository=repository,
        knowledge_retriever=knowledge_retriever,
    )

    request = RetrievalRequest(
        request_id="REAL_TEST_001",
        user_context=UserContext(user_id=REAL_USER_ID),
        intent_context=IntentContext(
            intent="claim_submission",
            confidence=0.95,
        ),
        policy_context=PolicyLookupContext(
            policy_number=REAL_POLICY_NUMBER,
        ),
    )

    response = service.retrieve(request)
    print("SERVICE RETRIEVAL RESPONSE:")
    print(response.model_dump_json(indent=2))
    assert response.status == "success"
    assert response.result.policy_data is not None
    assert response.result.policy_data.policy_number == REAL_POLICY_NUMBER

    print("\n=== Step 12: Test the actual Retrieval Agent ===")
    state = {
        "request_id": "REAL_TEST_001",
        "user_id": REAL_USER_ID,
        "intent": "claim_submission",
        "intent_confidence": 0.95,
        "policy_number": REAL_POLICY_NUMBER,
    }

    agent_result = retrieval_agent(state)
    print("AGENT RESULT:")
    print(json.dumps(agent_result, indent=2))
    assert "retrieval_response" in agent_result
    assert agent_result["retrieval_status"] == "success"
    assert agent_result["retrieval_response"]["result"]["policy_data"]["policy_number"] == REAL_POLICY_NUMBER

    print("\n ALL RETRIEVAL TESTS PASSED SUCCESSFULLY!")
