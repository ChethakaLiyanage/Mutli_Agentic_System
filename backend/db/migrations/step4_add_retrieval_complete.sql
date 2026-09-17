-- Step 4 lifecycle migration. This changes no rows and is safe to repeat.
alter table public.workflows
    drop constraint if exists workflows_current_status_check;

alter table public.workflows
    add constraint workflows_current_status_check check (current_status in (
        'received', 'intake_processing', 'intake_complete',
        'awaiting_clarification', 'manual_assistance_required',
        'information_retrieval', 'retrieval_complete', 'fraud_triage',
        'awaiting_human_review', 'guidance_processing', 'completed', 'failed'
    ));
