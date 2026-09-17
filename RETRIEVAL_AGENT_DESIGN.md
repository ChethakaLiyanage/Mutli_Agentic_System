# Retrieval Agent Input Contract Design
## Multi-Agentic Motor Insurance Claims System

This document defines the input contract for the Retrieval Agent (Step 1) in the multi-agent motor insurance claims system.

## Overview

The Retrieval Agent's responsibility is to retrieve authorized evidence needed by downstream agents (Fraud Detection and Reviewer Support). It does NOT:
- Approve or reject claims
- Determine fraud
- Calculate final fraud scores
- Invent missing identifiers
- Invent missing policy or claim information

## Design Principles Applied
- Modular: Clear separation of input groups
- Explainable: Each field has clear purpose and source
- Safe: No invented data, strict authorization boundaries
- Deterministic: Predictable structure for testing
- No hallucination: Only uses verified, provided data
- LangGraph compatible: Flat structure suitable for shared state
- Supabase ready: Clean field names for future database mapping
- Claim Intake compatible: Builds directly on existing output
- Testable: Clear validation rules and minimal viable inputs

## Retrieval Request Structure

```
RetrievalRequest
├── request_metadata
├── user_context  
├── intent_context
├── claim_context
├── policy_context
├── claim_lookup_context
├── document_references
└── retrieval_options
```

### A. Request Metadata
*Provided by: Orchestrator (system-generated)*

| Field Name | Data Type | Required | Provider | Purpose | Relevant Intents |
|------------|-----------|----------|----------|---------|------------------|
| `request_id` | string | Yes | Orchestrator (copied from Claim Intake) | Traceability across agent chain | All |
| `timestamp` | ISO datetime string | Yes | Orchestrator (system time) | Audit trail, caching invalidation | All |
| `agent_version` | string | No | Orchestrator | Debugging, version tracking | All |
| `correlation_id` | string | No | Orchestrator | Distributed tracing | All |

### B. User Context
*Provided by: Authentication/Session layer (before Orchestrator)*

| Field Name | Data Type | Required | Provider | Purpose | Relevant Intents |
|------------|-----------|----------|----------|---------|------------------|
| `user_id` | string | Yes* | Auth System | Authorization boundary - ensures user only accesses their own data | All (*Required for policy/claim access) |
| `session_id` | string | No | Auth System | Session tracking, audit trails | All |
| `authentication_method` | string | No | Auth System | Security context (password, OAuth, etc.) | All |
| `permissions` | list[string] | No | Auth System | Explicit permissions granted to user | All |

### C. Intent Context
*Provided by: Orchestrator (derived from Claim Intake output)*

| Field Name | Data Type | Required | Provider | Purpose | Relevant Intents |
|------------|-----------|----------|----------|---------|------------------|
| `primary_intent` | string | Yes | Orchestrator (from Claim Intake intent.label) | Determines retrieval strategy | All |
| `intent_confidence` | float | Yes | Orchestrator (from Claim Intake intent.confidence) | Affects retrieval urgency/thoroughness | All |
| `secondary_intents` | list[string] | No | Orchestrator | Additional intents detected | All |
| `requires_clarification` | boolean | Yes | Orchestrator (from Claim Intake) | Affects whether to proceed with retrieval | All |
| `missing_fields` | list[string] | Yes | Orchestrator (from Claim Intake) | Informs what cannot be retrieved | All |

### D. Claim Context
*Provided by: Claim Intake Agent (extracted from message)*

| Field Name | Data Type | Required | Provider | Purpose | Relevant Intents |
|------------|-----------|----------|----------|---------|------------------|
| `incident_type` | enum[string] | No | Claim Intake | Type of incident for filtering | claim_submission, policy_question, coverage_question, required_documents_question |
| `incident_date_text` | string | No | Claim Intake | Original date wording for context | claim_submission |
| `normalized_incident_date` | ISO date string | No | Claim Intake | Standardized date for queries | claim_submission |
| `incident_location` | string | No | Claim Intake | Location for jurisdiction/policy validation | claim_submission, policy_question |
| `damage_areas` | list[string] | No | Claim Intake | Vehicle damage for parts/labor estimation | claim_submission |
| `extracted_entities` | list[object] | No | Claim Intake | DATE/TIME/LOCATION entities for cross-reference | All |
| `insurance_type` | string | Yes | Claim Intake (hardcoded "motor") | Line of business filtering | All |

### E. Policy Context
*Provided by: Orchestrator (may come from auth/user context or external service)*

| Field Name | Data Type | Required | Provider | Purpose | Relevant Intents |
|------------|-----------|----------|----------|---------|------------------|
| `policy_id` | string | Conditional* | Orchestrator/User Context | Primary policy identifier | policy_question, coverage_question, required_documents_question, claim_submission (when available) |
| `policy_number` | string | Conditional* | Orchestrator/User Context | Human-readable policy ID | policy_question, coverage_question, required_documents_question, claim_submission (when available) |
| `policy_status` | enum[string] | No | Orchestrator | active/expired/cancelled for validation | policy_question, coverage_question |
| `coverage_details` | object | No | Orchestrator | Current coverage limits, deductibles | coverage_question |
| `policy_start_date` | ISO date | No | Orchestrator | Policy effective date | coverage_question |
| `policy_end_date` | ISO date | No | Orchestrator | Policy expiration date | coverage_question, required_documents_question |
| *Note: At least one of policy_id or policy_number is required when policy access is needed*

### F. Claim Lookup Context
*Provided by: Orchestrator (may come from external systems or user context)*

| Field Name | Data Type | Required | Provider | Purpose | Relevant Intents |
|------------|-----------|----------|----------|---------|------------------|
| `claim_id` | string | Conditional* | Orchestrator | Specific claim identifier | claim_status, claim_submission (for updates) |
| `claim_reference` | string | Conditional* | Orchestrator | Human-readable claim reference | claim_status |
| `vehicle_id` | string | No | Orchestrator | Vehicle-specific information | claim_submission, coverage_question |
| `customer_id` | string | Conditional* | Orchestrator/User Context | Customer identifier (may equal user_id) | policy_question, coverage_question, required_documents_question |
| *Note: claim_id or claim_reference required for claim_status; customer_id required for policy/customer questions*

### G. Document References
*Provided by: Orchestrator (from document upload tracking or user context)*

| Field Name | Data Type | Required | Provider | Purpose | Relevant Intents |
|------------|-----------|----------|----------|---------|------------------|
| `uploaded_document_ids` | list[string] | No | Orchestrator | IDs of documents already uploaded with this request | required_documents_question, claim_submission |
| `document_types_present` | list[string] | No | Orchestrator | Types of documents already available (photo, police_report, etc.) | required_documents_question |
| `pending_document_verification` | list[string] | No | Orchestrator | Documents uploaded but not yet verified | required_documents_question |

### H. Retrieval Options
*Provided by: Orchestrator (configuration/tuning parameters)*

| Field Name | Data Type | Required | Provider | Purpose | Relevant Intents |
|------------|-----------|----------|----------|---------|------------------|
| `max_results` | integer | No | Orchestrator | Limit number of returned records | All |
| `include_historical` | boolean | No | Orchestrator | Whether to include past claims/policies | claim_submission, policy_question |
| `historical_days_limit` | integer | No | Orchestrator | How far back to look for history | claim_submission, policy_question |
| `priority` | string | No | Orchestrator | Retrieval urgency (low, normal, high) | All |
| `timeout_seconds` | integer | No | Orchestrator | Maximum time to spend on retrieval | All |

## 3. Field Source Attribution Summary

### Fields Coming FROM Claim Intake Agent:
- incident_type
- incident_date_text
- normalized_incident_date
- incident_location
- damage_areas
- extracted_entities (DATE/TIME/LOCATION)
- insurance_type
- primary_intent (via Orchestrator transformation)
- intent_confidence (via Orchestrator transformation)
- requires_clarification (via Orchestrator transformation)
- missing_fields (via Orchestrator transformation)

### Fields Coming FROM Authentication/Session:
- user_id (REQUIRED for authorization)
- session_id
- authentication_method
- permissions

### Fields Coming FROM Orchestrator (computed/derived):
- request_id (pass-through)
- timestamp (system-generated)
- agent_version
- correlation_id
- secondary_intents
- policy_id/policy_number (may come from user profile service)
- policy_status, coverage_details, etc.
- claim_id/claim_reference/vehicle_id/customer_id
- uploaded_document_ids, document_types_present
- retrieval options (max_results, priority, etc.)

### Fields Coming FROM External Systems (future):
- All policy and claim context fields may eventually come from policy/customer management systems
- Document references may come from document management system

## 4. Fields That Should NOT Be Passed

The Retrieval Agent MUST NOT receive:
- `fraud_score` or `fraud_indicators` (belongs to Fraud Detection Agent)
- `approval_status` or `rejection_reason` (belongs to Reviewer Support/Human Officer)
- `final_decision` or `payout_amount` (belongs to Human Officer)
- `risk_level` or `risk_assessment` (belongs to Fraud Detection Agent)
- Any field that implies a decision has been made
- Invented or guessed identifiers
- Confidence scores for retrieved data (that's the retrieval agent's job to determine)

## 5. Minimum Input Requirements by Intent

### claim_submission
**Required:**
- request_id
- user_id (for authorization)
- primary_intent = "claim_submission"
- incident_type OR location OR normalized_incident_date (at least one claim detail)
- insurance_type

**Conditional (if available should be used):**
- policy_id or policy_number
- claim_id (if updating existing claim)
- damage_areas
- uploaded_document_ids

**Should NOT proceed if:**
- Missing ALL of: incident_type, location, normalized_incident_date (no claim details to retrieve on)

### policy_question
**Required:**
- request_id
- user_id (for authorization - MUST match policy owner)
- primary_intent = "policy_question"

**Conditional (at least one required):**
- policy_id OR policy_number
- customer_id (if looking up policies by customer)

### coverage_question
**Required:**
- request_id
- user_id (for authorization - MUST match policy owner)
- primary_intent = "coverage_question"

**Conditional (at least one required):**
- policy_id OR policy_number
- incident_type (to get relevant coverage)
- customer_id

### required_documents_question
**Required:**
- request_id
- user_id (for authorization - MUST match policy/claim owner)
- primary_intent = "required_documents_question"

**Conditional (at least one required):**
- policy_id OR policy_number OR claim_id
- incident_type (to get incident-specific requirements)
- uploaded_document_ids (to see what's already present)

### claim_status
**Required:**
- request_id
- user_id (for authorization - MUST match claim owner)
- primary_intent = "claim_status"

**Conditional (at least one required):**
- claim_id OR claim_reference
- policy_id OR policy_number (to look up recent claims)
- incident_date_text + location + incident_type (for fuzzy matching)

### general_information
**Required:**
- request_id
- user_id (may be optional for truly general info)
- primary_intent = "general_information"

**Notes:**
- May not require specific identifiers if retrieving general insurance information
- Still needs authorization check if user-specific info is involved

## 6. Validation Rules

### Authorization Rules
- user_id MUST match the owner of any policy/claim being accessed
- If user_id doesn't match resource owner, retrieval MUST return empty/not authorized
- No retrieval should occur without verified user_id

### Data Integrity Rules
- Identifiers (policy_id, claim_id, etc.) MUST NOT be guessed or invented
- If required identifier is missing and cannot be safely inferred, retrieval returns minimal/no results
- Dates must be valid ISO format or null
- Enums must be valid values or null

### Business Logic Rules
- claim_submission should not continue to fraud detection if requires_clarification = true AND missing critical claim fields
- Policy-specific retrieval requires authenticated customer context matching the policy
- Retrieval should only return records authorized for the authenticated user
- Historical data retrieval should respect privacy boundaries and consent

### Safety Rules
- Empty results are preferred over incorrect results
- Missing data should be explicitly indicated as missing, not inferred
- No field should ever contain fabricated information
- Conservative approach: when in doubt, return less rather than risk incorrect data

## 7. Example RetrievalRequests

### A. claim_submission Example
```json
{
  "request_metadata": {
    "request_id": "REQ001",
    "timestamp": "2026-09-17T10:30:00Z",
    "agent_version": "1.0.0",
    "correlation_id": "corr-abc-123"
  },
  "user_context": {
    "user_id": "user-789",
    "session_id": "sess-xyz-789",
    "authentication_method": "oauth2",
    "permissions": ["read_own_claims", "read_own_policy"]
  },
  "intent_context": {
    "primary_intent": "claim_submission",
    "intent_confidence": 0.85,
    "secondary_intents": [],
    "requires_clarification": false,
    "missing_fields": []
  },
  "claim_context": {
    "incident_type": "vehicle_collision",
    "incident_date_text": "yesterday",
    "normalized_incident_date": "2026-09-16",
    "incident_location": "Kandy",
    "damage_areas": ["left door"],
    "extracted_entities": [
      {"entity_type": "DATE", "value": "yesterday", "start": 17, "end": 26},
      {"entity_type": "LOCATION", "value": "Kandy", "start": 32, "end": 37}
    ],
    "insurance_type": "motor"
  },
  "policy_context": {
    "policy_id": "POL-456",
    "policy_number": "MOTOR/2024/7890",
    "policy_status": "active",
    "coverage_details": {
      "comprehensive": true,
      "third_party": true,
      "deductible": 500
    },
    "policy_start_date": "2024-01-15",
    "policy_end_date": "2025-01-15"
  },
  "claim_lookup_context": {
    "claim_id": null,
    "claim_reference": null,
    "vehicle_id": "VEH-123",
    "customer_id": "user-789"
  },
  "document_references": {
    "uploaded_document_ids": [],
    "document_types_present": [],
    "pending_document_verification": []
  },
  "retrieval_options": {
    "max_results": 10,
    "include_historical": true,
    "historical_days_limit": 730,
    "priority": "normal",
    "timeout_seconds": 5
  }
}
```

### B. coverage_question Example
```json
{
  "request_metadata": {
    "request_id": "REQ002",
    "timestamp": "2026-09-17T10:31:00Z",
    "agent_version": "1.0.0",
    "correlation_id": "corr-def-456"
  },
  "user_context": {
    "user_id": "user-789",
    "session_id": "sess-abc-456",
    "authentication_method": "oauth2",
    "permissions": ["read_own_policy"]
  },
  "intent_context": {
    "primary_intent": "coverage_question",
    "intent_confidence": 0.92,
    "secondary_intents": [],
    "requires_clarification": false,
    "missing_fields": ["policy_details"]
  },
  "claim_context": {
    "incident_type": null,
    "incident_date_text": null,
    "normalized_incident_date": null,
    "incident_location": null,
    "damage_areas": [],
    "extracted_entities": [],
    "insurance_type": "motor"
  },
  "policy_context": {
    "policy_id": "POL-456",
    "policy_number": "MOTOR/2024/7890",
    "policy_status": "active",
    "coverage_details": {
      "comprehensive": true,
      "third_party": true,
      "deductible": 500,
      "windscreen": true
    },
    "policy_start_date": "2024-01-15",
    "policy_end_date": "2025-01-15"
  },
  "claim_lookup_context": {
    "claim_id": null,
    "claim_reference": null,
    "vehicle_id": null,
    "customer_id": "user-789"
  },
  "document_references": {
    "uploaded_document_ids": [],
    "document_types_present": [],
    "pending_document_verification": []
  },
  "retrieval_options": {
    "max_results": 5,
    "include_historical": false,
    "historical_days_limit": 0,
    "priority": "normal",
    "timeout_seconds": 3
  }
}
```

### C. claim_status Example
```json
{
  "request_metadata": {
    "request_id": "REQ003",
    "timestamp": "2026-09-17T10:32:00Z",
    "agent_version": "1.0.0",
    "correlation_id": "corr-ghi-789"
  },
  "user_context": {
    "user_id": "user-789",
    "session_id": "sess-def-789",
    "authentication_method": "oauth2",
    "permissions": ["read_own_claims"]
  },
  "intent_context": {
    "primary_intent": "claim_status",
    "intent_confidence": 0.78,
    "secondary_intents": [],
    "requires_clarification": false,
    "missing_fields": []
  },
  "claim_context": {
    "incident_type": "theft_or_break_in",
    "incident_date_text": "2026-09-10",
    "normalized_incident_date": "2026-09-10",
    "incident_location": "Colombo",
    "damage_areas": [],
    "extracted_entities": [
      {"entity_type": "DATE", "value": "2026-09-10", "start": 11, "end": 21},
      {"entity_type": "LOCATION", "value": "Colombo", "start": 26, "end": 33}
    ],
    "insurance_type": "motor"
  },
  "policy_context": {
    "policy_id": "POL-456",
    "policy_number": "MOTOR/2024/7890",
    "policy_status": "active",
    "coverage_details": {
      "comprehensive": true,
      "theft": true,
      "deductible": 1000
    },
    "policy_start_date": "2024-01-15",
    "policy_end_date": "2025-01-15"
  },
  "claim_lookup_context": {
    "claim_id": "CLM-789",
    "claim_reference": "CLM/2026/00789",
    "vehicle_id": "VEH-123",
    "customer_id": "user-789"
  },
  "document_references": {
    "uploaded_document_ids": ["doc-001", "doc-002"],
    "document_types_present": ["photo", "police_report"],
    "pending_document_verification": ["doc-002"]
  },
  "retrieval_options": {
    "max_results": 1,
    "include_historical": true,
    "historical_days_limit": 365,
    "priority": "high",
    "timeout_seconds": 5
  }
}
```

## 8. Orchestrator Request Construction Guidelines

The Orchestrator should build the RetrievalRequest by combining:

### From Claim Intake Output:
- Copy request_id directly
- Transform intent.label → primary_intent
- Transform intent.confidence → intent_confidence
- Copy requires_clarification directly
- Copy missing_fields directly
- Extract claim_context fields (incident_type, date_text, normalized_date, location, damage_areas, entities, insurance_type)

### From Authenticated User/Session:
- user_id (from auth token/session)
- session_id (from session)
- authentication_method (from auth system)
- permissions (from auth/role system)

### From Available Identifier Services:
- policy_id/policy_number (from user profile service or claims database)
- claim_id/claim_reference (from claims database lookup)
- customer_id (from user profile - may equal user_id)
- vehicle_id (from vehicle registry or user profile)
- policy_status, coverage_details (from policy management system)
- document references (from document tracking system)

### Defaults and Fallbacks:
- Set reasonable defaults for retrieval_options (max_results=10, priority=normal, timeout=5s)
- Set timestamp to current system time
- Generate correlation_id if not provided by tracing system
- Set agent_version to current deployed version

## 9. Final Recommended Input Contract

Based on the analysis above, here is the final recommended input contract for the Retrieval Agent:

### Core Requirements
1. **Authorization is mandatory**: user_id must be present and validated
2. **No invented data**: All identifiers must come from trusted sources
3. **Conservative retrieval**: When uncertain, return less rather than risk incorrect data
4. **Intent-driven**: Different intents trigger different retrieval strategies
5. **Traceable**: Every request must be traceable through the system

### Minimal Viable Input by Intent

| Intent | Absolute Minimum | Recommended Minimum |
|--------|------------------|---------------------|
| claim_submission | request_id, user_id, primary_intent="claim_submission" | + incident details (type/location/date) + policy identifiers |
| policy_question | request_id, user_id, primary_intent="policy_question" | + policy_id OR policy_number OR customer_id |
| coverage_question | request_id, user_id, primary_intent="coverage_question" | + policy_id OR policy_number + (incident_type OR customer_id) |
| required_documents_question | request_id, user_id, primary_intent="required_documents_question" | + policy_id OR policy_number OR claim_id |
| claim_status | request_id, user_id, primary_intent="claim_status" | + claim_id OR claim_reference |
| general_information | request_id, user_id, primary_intent="general_information" | + (optional: user-specific context if needed) |

### Validation Priority Order
1. **Authorization**: Verify user_id and permissions
2. **Intent validation**: Ensure primary_intent is valid
3. **Identifier validation**: Check that provided identifiers are properly formatted
4. **Business rule validation**: Apply intent-specific requirements
5. **Execution**: Proceed with retrieval using validated inputs

This contract provides a solid foundation for Step 2 (implementation) while maintaining safety, clarity, and extensibility.

---
*Document created in branch: feature/retrieval-agent-design*
*Author: Chethaka D Liyanage*
*Date: 2026-09-17*