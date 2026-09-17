-- Step 7: grounded Agent 4 guidance lifecycle.
-- Existing workflows and all earlier lifecycle statuses are preserved.

alter table public.workflows
    add column if not exists guidance_result jsonb;

alter table public.workflows
    drop constraint if exists workflows_current_status_check;

alter table public.workflows
    add constraint workflows_current_status_check check (current_status in (
        'received', 'intake_processing', 'intake_complete',
        'awaiting_clarification', 'manual_assistance_required',
        'information_retrieval', 'retrieval_complete',
        'claim_information_retrieval', 'fraud_triage',
        'awaiting_human_review', 'approved', 'rejected',
        'more_information_required', 'escalated',
        'guidance_processing', 'guidance_generation', 'completed', 'failed'
    ));
