-- Durable application persistence for the motor-insurance prototype.
-- Run this in the Supabase SQL editor before selecting the Supabase backend.
-- The backend uses a server-side service-role key; complex RLS is deferred.

create table if not exists public.users (
    user_id text primary key,
    email text not null unique,
    password_hash text not null,
    role text not null check (role in ('customer', 'claims_officer', 'admin')),
    created_at timestamptz not null
);

create table if not exists public.workflows (
    workflow_id text primary key,
    request_id text not null,
    last_request_id text not null,
    raw_text text not null,
    original_text text not null,
    accumulated_text text not null,
    clarification_count integer not null default 0 check (clarification_count >= 0),
    authenticated_user_id text not null references public.users(user_id),
    authenticated_user_role text not null
        check (authenticated_user_role in ('customer', 'claims_officer', 'admin')),
    intake_result jsonb,
    retrieval_result jsonb,
    fraud_result jsonb,
    human_review_result jsonb,
    guidance_result jsonb,
    workflow_type text not null,
    current_status text not null,
    missing_fields jsonb not null default '[]'::jsonb,
    requires_clarification boolean not null default false,
    errors jsonb not null default '[]'::jsonb,
    audit_trail jsonb not null default '[]'::jsonb,
    created_at timestamptz not null,
    updated_at timestamptz not null
);

-- The users.email unique constraint already creates its query index.
create index if not exists idx_workflows_authenticated_user_id
    on public.workflows(authenticated_user_id);
create index if not exists idx_workflows_current_status
    on public.workflows(current_status);
create index if not exists idx_workflows_created_at
    on public.workflows(created_at);

-- Defense in depth: application updates may not transfer workflow ownership
-- or rewrite its creation timestamp.
create or replace function public.protect_workflow_identity()
returns trigger
language plpgsql
as $$
begin
    if new.authenticated_user_id is distinct from old.authenticated_user_id then
        raise exception 'workflow ownership cannot change';
    end if;
    if new.created_at is distinct from old.created_at then
        raise exception 'workflow creation time cannot change';
    end if;
    return new;
end;
$$;

drop trigger if exists protect_workflow_identity_update on public.workflows;
create trigger protect_workflow_identity_update
before update on public.workflows
for each row execute function public.protect_workflow_identity();
