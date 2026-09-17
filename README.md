# Multi-Agentic Motor Insurance Claims and Policy Support

This university project is building a multi-agent backend for motor-insurance
claims and policy support. The backend currently includes **Agent 1: Claim
Intake & Query Understanding**, an authenticated Orchestrator with multi-turn
clarification, and interchangeable in-memory or Supabase persistence.

## Claim Intake Agent

Agent 1 accepts a customer's free-text motor-insurance message and converts it
into a validated JSON structure for a future Orchestrator. It performs intent
classification and grounded claim-detail extraction without using an LLM or
inventing facts that are not present in the message.

### Supported intents

- `claim_submission`
- `policy_question`
- `coverage_question`
- `required_documents_question`
- `claim_status`
- `general_information`

### Supported incident types

- `vehicle_collision`
- `windscreen_damage`
- `flood_damage`
- `theft_or_break_in`

Incident types are detected with controlled keyword and phrase rules. The agent
returns `null` when the message does not provide enough evidence.

### Supported damage areas

- `front bumper`
- `rear bumper`
- `left door`
- `right door`
- `windscreen`
- `windshield`
- `bonnet`
- `boot`
- `headlight`
- `tail light`
- `mirror`
- `roof`
- `wheel`
- `tyre`

Multiple damage areas can be returned in their original text order. Common
variants such as plural forms, `tire`, and `side mirror` are normalized to this
controlled vocabulary.

### Extracted fields

The response can contain:

- predicted intent and probability confidence;
- incident type;
- original date wording and an ISO-normalized date;
- the first grounded location found in the message;
- controlled vehicle damage areas;
- mapped `DATE`, `TIME`, and `LOCATION` entities with source offsets;
- claim-submission fields that are missing; and
- whether clarification is required.

### Processing pipeline

```text
IntakeRequest
    -> deterministic preprocessing for intent classification
    -> TF-IDF + Logistic Regression intent prediction
    -> spaCy entity extraction from the original text
    -> rule-based incident and damage extraction
    -> deterministic date extraction and normalization
    -> missing-field and clarification checks
    -> IntakeResponse
```

The original message is retained for entity and claim-detail extraction. The
classification copy is trimmed, lowercased, stripped of unnecessary punctuation,
and normalized to single whitespace. Internal punctuation useful for dates,
times, registrations, and policy-like identifiers is preserved where possible.

### Intent classifier

The classifier uses:

- a balanced CSV dataset containing 240 messages, with 40 examples per intent;
- the same deterministic preprocessing used at runtime;
- `TfidfVectorizer(ngram_range=(1, 2))`; and
- multiclass Logistic Regression with probability output.

The persisted model is committed at
`backend/app/nlp/models/intent_classifier.joblib`. Runtime requests load and
cache this artifact; they do not retrain the model. The dataset is committed at
`backend/data/intent_training.csv`.

To explicitly retrain, evaluate, and overwrite the persisted model:

```powershell
python backend/scripts/train_intent_classifier.py
```

The current measured held-out evaluation used a stratified 80/20 split with
192 training samples and 48 test samples:

| Metric | Value |
|---|---:|
| Accuracy | 0.8333 |
| Macro precision | 0.8397 |
| Macro recall | 0.8333 |
| Macro F1-score | 0.8296 |

The confusion-matrix label order was:

```text
claim_submission
policy_question
coverage_question
required_documents_question
claim_status
general_information
```

```text
[[6, 0, 1, 0, 1, 0],
 [0, 6, 1, 0, 0, 1],
 [0, 0, 8, 0, 0, 0],
 [0, 0, 0, 8, 0, 0],
 [0, 0, 0, 0, 7, 1],
 [0, 1, 0, 1, 1, 5]]
```

On that split, `coverage_question` and `required_documents_question` had full
recall. The largest overlap involved `general_information`, which was sometimes
confused with policy, document, or claim-status language.

### Clarification behavior

For `claim_submission`, the agent checks for:

- `incident_type`
- `incident_date`
- `location`

Only genuinely absent fields are added to `missing_fields`. Other intents do not
automatically require these claim-submission details.

`requires_clarification` becomes `true` when a required claim field is missing
or intent confidence is below the configurable default threshold of `0.50`.
Clarification-question text is not generated yet.

## Setup

Run these commands from the repository root:

```powershell
python -m pip install -r backend/requirements.txt
python -m spacy download en_core_web_sm
```

Copy `.env.example` to `.env` and replace development placeholders when using
authentication or durable persistence. The `.env` file is ignored by Git.

## Persistence backends

The authentication and Orchestrator services use repository interfaces, with
two interchangeable implementations:

- `memory` is the default and requires no external database. Users and workflows
  disappear when the process stops.
- `supabase` stores application-managed users and workflow state in Supabase
  Postgres. Supabase is used only as a database; authentication remains the
  project's Argon2id and JWT implementation.

To prepare Supabase, run `backend/db/schema.sql` in the Supabase SQL editor and
configure:

```env
PERSISTENCE_BACKEND=supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_SERVICE_ROLE_KEY=replace-with-your-service-role-key
```

For local memory mode:

```env
PERSISTENCE_BACKEND=memory
```

The service-role key is server-side only and must never be exposed to a browser
or committed. The application creates one shared Supabase client and maps rows
back into the same domain models used by the in-memory repositories. If
Supabase mode is selected without its required configuration, application
initialization fails instead of silently falling back to memory.

The schema keeps ownership, workflow status, type, and timestamps as ordinary
columns while storing nested agent results and audit history as JSONB. Complex
Row Level Security policies are deferred; application ownership checks remain
mandatory and server-side service-role access is used by this prototype.

## Run the API

From the repository root:

```powershell
python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8000 --reload
```

Open the interactive API documentation at:

```text
http://127.0.0.1:8000/docs
```

## Frontend foundation

The React, Vite, and TypeScript frontend in `frontend/` currently provides
registration, login, authenticated-session restoration, logout, protected
routing, and a basic dashboard shell. Claim-assistant and downstream agent
interfaces are intentionally deferred to the next frontend step.

Create `frontend/.env` from `frontend/.env.example`, then run:

```powershell
cd frontend
npm install
npm run dev
```

The development UI is available at `http://localhost:5173`. The backend allows
requests only from `http://localhost:5173` and `http://127.0.0.1:5173` for local
frontend development. Only `VITE_API_BASE_URL` belongs in the frontend
environment; server secrets must remain in the backend environment.

### Health endpoint

```http
GET /health
```

```json
{
  "status": "ok",
  "service": "claim-intake-agent"
}
```

## API contract

### Analyze a message

```http
POST /intake/analyze
Content-Type: application/json
```

Request:

```json
{
  "request_id": "REQ001",
  "text": "A bus hit my car yesterday near Kandy and damaged the left door."
}
```

Response:

```json
{
  "request_id": "REQ001",
  "agent": "claim_intake",
  "status": "success",
  "data": {
    "intent": {
      "label": "claim_submission",
      "confidence": 0.55
    },
    "insurance_type": "motor",
    "incident": {
      "type": "vehicle_collision",
      "date_text": "yesterday",
      "normalized_date": "2026-09-15",
      "location": "Kandy"
    },
    "damage": {
      "areas": ["left door"],
      "description": null
    },
    "entities": [
      {
        "entity_type": "DATE",
        "value": "yesterday",
        "start": 17,
        "end": 26,
        "confidence": null
      },
      {
        "entity_type": "LOCATION",
        "value": "Kandy",
        "start": 32,
        "end": 37,
        "confidence": null
      }
    ],
    "missing_fields": [],
    "requires_clarification": false
  },
  "errors": []
}
```

The confidence value is illustrative. The API always returns the probability
calculated by the persisted classifier. Relative normalized dates depend on the
date on which the request is processed.

Invalid request bodies return HTTP `422`. Unexpected route-level failures return
HTTP `500` with a generic message; internal exception details are logged but are
not exposed in the response.

## Testing

Run the complete backend test suite:

```powershell
python -m pytest backend/tests -v
```

Run only the Claim Intake Agent integration and API tests:

```powershell
python -m pytest backend/tests/test_claim_intake_agent.py backend/tests/test_intake_api.py -v
```

Run all Agent 1 NLP component tests:

```powershell
python -m pytest backend/tests/test_preprocessing.py backend/tests/test_intent_classifier.py backend/tests/test_claim_detail_extraction.py -v
```

## Orchestrator integration

Authenticated customers create and resume workflows through:

```http
POST /orchestrator/process
POST /orchestrator/workflows/{workflow_id}/clarify
```

The Orchestrator stores the complete Agent 1 response, maps intent to a future
workflow type, and either returns `intake_complete` or pauses at
`awaiting_clarification`. It preserves ownership and audit history across
clarification turns. Agents 2–4 are not executed yet.

## Portability and model handling

- Source code contains no absolute user-specific paths.
- Dataset and model paths are resolved relative to the installed project files.
- Commands work from the project root on Windows, macOS, or Linux through
  `python -m ...` invocation.
- No secrets or API keys are embedded in the source.
- The trained joblib model is committed so a fresh checkout can predict without
  retraining.
- The spaCy `en_core_web_sm` package must be installed separately because it is
  not distributed through the normal project requirements file.
- Persisted scikit-learn/joblib artifacts should only be loaded from this trusted
  repository, not from untrusted sources.

## Current limitations

- Intent confidence is modest because the training dataset has 240 examples.
- Only the first extracted location is selected.
- Only the earliest supported date expression is normalized.
- Rule-based incident extraction has limited vocabulary.
- Damage extraction uses a controlled vocabulary.
- Vehicle, policy, and claim identifiers are not yet extracted as structured
  fields.
- Clarification-question generation is not implemented.
- Location and general-entity quality depend on `en_core_web_sm`.
- In-memory persistence is process-local; Supabase mode requires the supplied
  SQL schema and server-side credentials.
- JWT refresh, revocation, password reset, and advanced account administration
  are not implemented.
- Agents 2–4, LangGraph orchestration, LLM integration, and frontend work are
  not implemented yet.
