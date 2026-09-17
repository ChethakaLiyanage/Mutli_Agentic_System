-- Step 5: durable claim/fraud orchestration additions.
-- Safe and non-destructive: existing workflow and claim rows are preserved.

alter table public.workflows
    add column if not exists claim_context jsonb;

alter table public.claims
    add column if not exists workflow_id text references public.workflows(workflow_id);

create unique index if not exists uq_claims_workflow_id
    on public.claims(workflow_id)
    where workflow_id is not null;

alter table public.workflows
    drop constraint if exists workflows_current_status_check;

alter table public.workflows
    add constraint workflows_current_status_check check (current_status in (
        'received', 'intake_processing', 'intake_complete',
        'awaiting_clarification', 'manual_assistance_required',
        'information_retrieval', 'retrieval_complete',
        'claim_information_retrieval', 'fraud_triage',
        'awaiting_human_review', 'guidance_processing', 'completed', 'failed'
    ));
