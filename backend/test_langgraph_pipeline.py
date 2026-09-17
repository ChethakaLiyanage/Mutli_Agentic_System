import sys
from pathlib import Path

repo_root = str(Path(__file__).resolve().parent.parent)
backend_dir = str(Path(__file__).resolve().parent)
for path in (repo_root, backend_dir):
    if path not in sys.path:
        sys.path.insert(0, path)

import json
from backend.app.graph.workflow import create_claims_workflow

print('=== 1. Compiling Claims Workflow ===')
workflow = create_claims_workflow()
print('Workflow compiled successfully.')

print('\n=== 2. Invoking LangGraph with claim_submission intent ===')
claim_submission_state = {
    'request_id': 'GRAPH_REAL_001',
    'user_id': '03f4068e-aa25-467b-8d99-c1fb08fa384f',
    'intent': 'claim_submission',
    'intent_confidence': 0.95,
    'policy_number': 'MTR-DEMO-1001',
    'incident_type': 'motor_accident',
    'incident_date': '2026-09-15',
    'incident_location': 'Colombo',
    'claimed_amount': 250000.0,
    'incident_description': 'Vehicle collision near Colombo.',
}

result_submission = workflow.invoke(claim_submission_state)

print('\n--- Retrieval Agent Output in State ---')
assert result_submission['retrieval_status'] == 'success'
print('retrieval_status:', result_submission['retrieval_status'])
policy_data = result_submission['retrieval_response']['result']['policy_data']
print('Retrieved Policy Number:', policy_data['policy_number'])
print('Retrieved Customer ID:', policy_data['customer_id'])

print('\n--- Next Agent (fraud_detection_agent) Received retrieval_response ---')
assert 'fraud_assessment' in result_submission, 'fraud_assessment not found! Next agent did not execute properly.'
print('Risk Level:', result_submission['fraud_assessment']['risk_level'])
print('Risk Score:', result_submission['fraud_assessment']['risk_score'])
print('Recommended Action:', result_submission['fraud_assessment']['recommended_action'])

print('\n--- Downstream Agent (guidance_agent / reviewer_support_agent) Received State ---')
assert 'guidance_response' in result_submission, 'guidance_response not found in state!'
print('Guidance Status:', result_submission['guidance_response']['status'])
print('Guidance Response Type:', result_submission['guidance_response']['response_type'])
print('Guidance Message:', result_submission['guidance_response']['data']['message'])
print('Next Step:', result_submission.get('next_step'))

print('\n=== 3. Invoking LangGraph with policy_question intent ===')
policy_query_state = {
    'request_id': 'GRAPH_REAL_002',
    'user_id': '03f4068e-aa25-467b-8d99-c1fb08fa384f',
    'intent': 'policy_question',
    'intent_confidence': 0.92,
    'policy_number': 'MTR-DEMO-1001',
}

result_policy = workflow.invoke(policy_query_state)
print('Policy query retrieval_status:', result_policy['retrieval_status'])
assert result_policy['retrieval_status'] == 'success'
assert 'fraud_assessment' not in result_policy, 'fraud_detection_agent should have been skipped for policy_question!'
assert 'guidance_response' in result_policy

print('\n ALL LANGGRAPH PIPELINE VERIFICATIONS PASSED!')
