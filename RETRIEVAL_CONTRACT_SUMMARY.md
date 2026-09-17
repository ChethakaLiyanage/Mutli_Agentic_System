# Retrieval Agent Input Contract - Summary

## Core Purpose
The Retrieval Agent retrieves authorized evidence needed by downstream agents (Fraud Detection, Reviewer Support). It does NOT make decisions, calculate scores, or invent data.

## Input Structure
```
RetrievalRequest
├── request_metadata      # System tracking (Orchestrator)
├── user_context         # Auth info (Auth System) 
├── intent_context       # From Claim Intake (via Orchestrator)
├── claim_context        # Extracted from message (Claim Intake)
├── policy_context       # Policy info (Orchestrator/User Service)
├── claim_lookup_context # Claim/vehicle IDs (Orchestrator)
├── document_references  # Uploaded docs (Orchestrator)
└── retrieval_options    # Config params (Orchestrator)
```

## Key Principles
- ✅ **No invented data**: Only use provided, verified identifiers
- ✅ **Authorization first**: user_id required for all policy/claim access
- ✅ **Intent-driven**: Different retrieval strategies per intent
- ✅ **Conservative**: Return less data rather than risk incorrect data
- ✅ **Traceable**: Full audit trail through request_id/timestamp
- ✅ **Safe boundaries**: Never access unauthorized user data

## Minimum Requirements by Intent

| Intent | Absolute Minimum |
|--------|------------------|
| claim_submission | request_id, user_id, primary_intent="claim_submission" |
| policy_question | request_id, user_id, primary_intent="policy_question" |
| coverage_question | request_id, user_id, primary_intent="coverage_question" |
| required_documents_question | request_id, user_id, primary_intent="required_documents_question" |
| claim_status | request_id, user_id, primary_intent="claim_status" |
| general_information | request_id, user_id, primary_intent="general_information" |

## Critical Validation Rules
1. **Authorization**: user_id must match resource owner
2. **No guessing**: Identifiers must come from trusted sources
3. **Intent validation**: Verify primary_intent is valid
4. **Business rules**: Apply intent-specific requirements
5. **Safety first**: Prefer empty results over incorrect data

## Field Sources
- **Claim Intake**: incident_type, dates, location, damage, entities, intent data
- **Auth System**: user_id, session_id, permissions  
- **Orchestrator**: request_id, timestamp, computed context, policy/claim IDs
- **External Services**: policy details, claim history, document info (future)

## What's Excluded
- ❌ Fraud scores/indicators (Fraud Detection's job)
- ❌ Approval/rejection decisions (Human Officer's job)  
- ❌ Invented identifiers or data
- ❌ Confidence scores for retrieved data
- ❌ Any decision-making fields

## Next Step (Step 2)
Implement the Retrieval Agent using this contract, with:
- Pydantic validation
- Authorization checks
- Intent-based routing to retrieval strategies
- Safe, conservative data retrieval
- Proper error handling for missing/unauthorized data

---
*Branch: feature/retrieval-agent-design*
*Created: 2026-09-17*