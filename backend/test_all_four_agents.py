import sys
from pathlib import Path

repo_root = str(Path(__file__).resolve().parent.parent)
backend_dir = str(Path(__file__).resolve().parent)
for path in (repo_root, backend_dir):
    if path not in sys.path:
        sys.path.insert(0, path)

import json
from backend.app.agents.claim_intake_agent import ClaimIntakeAgent
from backend.app.schemas.intake import IntakeRequest
from backend.app.agents.retrieval_agent import retrieval_agent
from backend.app.agents.fraud_detection_agent import fraud_detection_agent
from backend.app.agents.guidance_agent import guidance_agent


def test_all_four_agents():
    print("=" * 70)
    print("   TESTING ALL 4 AGENTS IN PIPELINE: INTAKE -> RETRIEVAL -> FRAUD -> GUIDANCE")
    print("=" * 70)

    # -------------------------------------------------------------
    # AGENT 1: Claim Intake & Query Understanding Agent
    # -------------------------------------------------------------
    print("\n[AGENT 1] CLAIM INTAKE AGENT")
    print("-" * 50)
    raw_text = (
        "A bus collided with my vehicle yesterday near Colombo and damaged the left door. "
        "My policy number is MTR-DEMO-1001. Claimed amount is 250000."
    )
    print(f"Customer Input Text:\n\"{raw_text}\"\n")

    intake_agent = ClaimIntakeAgent()
    intake_request = IntakeRequest(
        request_id="ALL_AGENTS_TEST_001",
        text=raw_text,
    )
    intake_result = intake_agent.analyze(intake_request)
    print(f"Status:             {intake_result.status}")
    print(f"Intent Label:       {intake_result.data.intent.label}")
    print(f"Confidence:         {intake_result.data.intent.confidence:.2f}")
    print(f"Incident Type:      {intake_result.data.incident.type}")
    print(f"Incident Date:      {intake_result.data.incident.normalized_date}")
    print(f"Incident Location:  {intake_result.data.incident.location}")
    print(f"Damage Areas:       {intake_result.data.damage.areas}")
    print(f"Requires Clarif:    {intake_result.data.requires_clarification}")

    assert intake_result.status == "success"
    assert intake_result.data.intent.label == "claim_submission"
    print(">>> Agent 1 (Intake) PASSED.")

    # -------------------------------------------------------------
    # AGENT 2: Information Retrieval (IR) Agent
    # -------------------------------------------------------------
    print("\n[AGENT 2] RETRIEVAL AGENT")
    print("-" * 50)
    # Extract policy_number and claimed_amount from text or entities
    policy_number = "MTR-DEMO-1001"
    for entity in intake_result.data.entities:
        if entity.entity_type == "POLICY_NUMBER":
            policy_number = entity.value

    # Build shared graph state from Agent 1 output
    state = {
        "request_id": intake_request.request_id,
        "user_id": "03f4068e-aa25-467b-8d99-c1fb08fa384f",
        "intent": intake_result.data.intent.label,
        "intent_confidence": intake_result.data.intent.confidence,
        "policy_number": policy_number,
        "incident_type": intake_result.data.incident.type,
        "incident_date": intake_result.data.incident.normalized_date,
        "incident_location": intake_result.data.incident.location,
        "damage_areas": intake_result.data.damage.areas,
        "claimed_amount": 250000.0,
        "incident_description": raw_text,
    }

    state_after_retrieval = retrieval_agent(state)
    print(f"Retrieval Status:   {state_after_retrieval.get('retrieval_status')}")

    retrieval_resp = state_after_retrieval.get("retrieval_response", {})
    ret_result = retrieval_resp.get("result", {})
    policy_data = ret_result.get("policy_data", {})
    hist_claims = ret_result.get("historical_claims", [])

    print(f"Policy Number:      {policy_data.get('policy_number')}")
    print(f"Policy Status:      {policy_data.get('status')}")
    print(f"Customer ID:        {policy_data.get('customer_id')}")
    print(f"Historical Claims:  {len(hist_claims)} record(s)")

    assert state_after_retrieval.get("retrieval_status") == "success"
    assert policy_data.get("policy_number") == "MTR-DEMO-1001"
    print(">>> Agent 2 (Retrieval) PASSED.")

    # -------------------------------------------------------------
    # AGENT 3: Fraud Detection & ML Anomaly Scoring Agent
    # -------------------------------------------------------------
    print("\n[AGENT 3] FRAUD DETECTION AGENT")
    print("-" * 50)
    state_after_fraud = fraud_detection_agent(state_after_retrieval)
    fraud_assessment = state_after_fraud.get("fraud_assessment", {})

    print(f"Risk Level:         {fraud_assessment.get('risk_level')}")
    print(f"Risk Score:         {fraud_assessment.get('risk_score')}")
    print(f"Rule Score:         {fraud_assessment.get('rule_score')}")
    print(f"ML Anomaly Score:   {fraud_assessment.get('ml_anomaly_score')}")
    print(f"Recommended Action: {fraud_assessment.get('recommended_action')}")
    print(f"Automated Decision: {fraud_assessment.get('automated_decision')}")

    assert "fraud_assessment" in state_after_fraud
    assert fraud_assessment.get("risk_level") in ("low", "medium", "high")
    assert fraud_assessment.get("automated_decision") is False
    print(">>> Agent 3 (Fraud Detection) PASSED.")

    # -------------------------------------------------------------
    # AGENT 4: Guidance / Reviewer Support Agent
    # -------------------------------------------------------------
    print("\n[AGENT 4] GUIDANCE & REVIEWER SUPPORT AGENT")
    print("-" * 50)
    state_after_guidance = guidance_agent(state_after_fraud)
    guidance_resp = state_after_guidance.get("guidance_response", {})
    guidance_data = guidance_resp.get("data", {})

    print(f"Guidance Status:    {guidance_resp.get('status')}")
    print(f"Response Type:      {guidance_resp.get('response_type')}")
    print(f"Agent Name:         {guidance_resp.get('agent')}")
    print(f"Message:            {guidance_data.get('message')}")
    print(f"Next Step:          {state_after_guidance.get('next_step')}")

    assert guidance_resp.get("status") == "success"
    assert guidance_resp.get("agent") == "guidance_agent"
    assert state_after_guidance.get("next_step") == "human_reviewer"
    print(">>> Agent 4 (Guidance / Reviewer Support) PASSED.")

    print("\n" + "=" * 70)
    print("   ALL 4 AGENTS EXECUTED AND PASSED SUCCESSFULLY!")
    print("=" * 70)


if __name__ == "__main__":
    test_all_four_agents()
