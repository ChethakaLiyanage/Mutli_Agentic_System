-- Step 9: Finalize claim submission flow
-- Adds new workflow statuses for document submission, fraud triage, staff summary, assignment, and officer review.
-- Creates claim_assignments and notifications tables.

alter table public.workflows
    drop constraint if exists workflows_current_status_check;

alter table public.workflows
    add constraint workflows_current_status_check check (current_status in (
        'received', 'intake_processing', 'intake_complete',
        'awaiting_clarification', 'manual_assistance_required',
        'information_retrieval', 'retrieval_complete',
        'claim_information_retrieval', 'awaiting_documents',
        'documents_submitted', 'fraud_triage', 'fraud_triage_complete',
        'review_summary_generation', 'awaiting_assignment',
        'under_human_review', 'awaiting_human_review',
        'approved', 'rejected', 'more_information_required', 'escalated',
        'guidance_processing', 'guidance_generation', 'completed', 'failed'
    ));

-- Ensure reviewer_guidance_result column exists if not added
alter table if exists public.workflows
    add column if not exists reviewer_guidance_result jsonb;

-- Table for tracking officer claim assignments
create table if not exists public.claim_assignments (
    assignment_id text primary key default gen_random_uuid()::text,
    claim_id text not null references public.claims(claim_id),
    workflow_id text not null references public.workflows(workflow_id),
    assigned_to text not null references public.users(user_id),
    assigned_by text not null references public.users(user_id),
    assigned_at timestamptz not null default now()
);

create index if not exists idx_claim_assignments_claim_id on public.claim_assignments(claim_id);
create index if not exists idx_claim_assignments_workflow_id on public.claim_assignments(workflow_id);
create index if not exists idx_claim_assignments_assigned_to on public.claim_assignments(assigned_to);

-- Table for customer notifications
create table if not exists public.notifications (
    id text primary key default gen_random_uuid()::text,
    user_id text not null references public.users(user_id),
    workflow_id text references public.workflows(workflow_id),
    claim_id text references public.claims(claim_id),
    type text not null,
    title text not null,
    message text not null,
    is_read boolean not null default false,
    created_at timestamptz not null default now(),
    read_at timestamptz
);

create index if not exists idx_notifications_user_id on public.notifications(user_id);
create index if not exists idx_notifications_is_read on public.notifications(is_read);
create index if not exists idx_notifications_created_at on public.notifications(created_at);
