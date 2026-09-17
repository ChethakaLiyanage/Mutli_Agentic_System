# Database setup and migration

`schema.sql` is the canonical backend persistence contract. It creates missing
objects without dropping tables or deleting rows.

## Fresh Supabase project

1. Open the Supabase SQL editor and review `backend/db/schema.sql`.
2. Run the file, then run it again to confirm the setup is idempotent.
3. Keep `SUPABASE_URL` and `SUPABASE_SERVICE_ROLE_KEY` in the backend runtime
   environment only. Never expose the service-role key to the frontend.
4. Set `PERSISTENCE_BACKEND=supabase` only after verification passes.

The application does not apply database schema changes at startup.

For databases created before Combined Integration Step 5, run
`backend/db/migrations/step5_add_claim_fraud_workflow.sql` manually. It adds
the nullable canonical claim snapshot, a stable workflow-to-claim link, and
the `claim_information_retrieval` status without deleting existing rows.

For databases created before Combined Integration Step 6, apply
`backend/db/migrations/step6_add_human_review_lifecycle.sql` after the Step 5
migration. It adds reviewer attribution/reason fields, final review statuses,
one-decision-per-workflow enforcement, and an atomic decision transaction.

For a database created before Orchestrator Integration Step 4, apply
`backend/db/migrations/step4_add_retrieval_complete.sql` once through the SQL
editor. It only replaces the workflow-status check constraint and does not
modify workflow rows.

## Existing or legacy project

`CREATE TABLE IF NOT EXISTS` does not change an existing table. Inspect and
back up populated tables before applying a reviewed migration. Known legacy
column names are:

| Legacy column | Canonical column |
| --- | --- |
| `policies.id` | `policies.policy_id` |
| `claims.id` | `claims.claim_id` |
| `claims.claim_type` | `claims.incident_type` |
| `claims.status` | `claims.claim_status` |
| `claim_documents.id` | `claim_documents.document_id` |
| `fraud_assessments.ml_anomaly_score` | `fraud_assessments.anomaly_score` |
| `fraud_assessments.risk_indicators` | `fraud_assessments.indicators` |

For existing data, rename columns, backfill nulls, validate controlled values,
and only then add constraints. Do not drop populated tables to match this file.

## Verification

```powershell
$env:PYTHONPATH='backend'
python -m pytest backend/tests/test_database_contracts.py -v
```

Optional live checks are read-only and opt-in. They issue zero-row `select`
requests to confirm table visibility and never create or alter tables.
