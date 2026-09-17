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
