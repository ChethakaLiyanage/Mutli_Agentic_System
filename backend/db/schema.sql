-- Canonical persistence schema for the motor-insurance prototype.
-- Safe for a fresh database: statements create missing objects and do not delete data.
-- Existing legacy tables need a reviewed migration because IF NOT EXISTS does not alter them.

create extension if not exists pgcrypto;

create table if not exists public.users (
    user_id text primary key,
    email text not null unique,
    password_hash text not null,
    role text not null check (role in ('customer', 'claims_officer', 'admin')),
    created_at timestamptz not null default now()
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
    authenticated_user_role text not null check (authenticated_user_role in ('customer', 'claims_officer', 'admin')),
    intake_result jsonb,
    claim_context jsonb,
    retrieval_result jsonb,
    fraud_result jsonb,
    human_review_result jsonb,
    guidance_result jsonb,
    reviewer_guidance_result jsonb,
    workflow_type text not null check (workflow_type in (
        'information_request', 'claim_submission', 'claim_status', 'clarification', 'unknown'
    )),
    current_status text not null check (current_status in (
        'received', 'intake_processing', 'intake_complete', 'awaiting_clarification',
        'manual_assistance_required', 'information_retrieval',
        'claim_information_retrieval', 'fraud_triage',
        'retrieval_complete', 'awaiting_human_review', 'guidance_processing',
        'guidance_generation',
        'approved', 'rejected', 'more_information_required', 'escalated',
        'completed', 'failed'
    )),
    missing_fields jsonb not null default '[]'::jsonb check (jsonb_typeof(missing_fields) = 'array'),
    requires_clarification boolean not null default false,
    errors jsonb not null default '[]'::jsonb check (jsonb_typeof(errors) = 'array'),
    audit_trail jsonb not null default '[]'::jsonb check (jsonb_typeof(audit_trail) = 'array'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.policies (
    policy_id text primary key,
    policy_number text not null unique,
    customer_id text not null references public.users(user_id),
    insurance_type text not null default 'motor',
    status text not null check (status in ('active', 'expired', 'cancelled')),
    start_date date not null,
    end_date date not null,
    coverage_details jsonb not null default '{}'::jsonb check (jsonb_typeof(coverage_details) = 'object'),
    exclusions jsonb not null default '[]'::jsonb check (jsonb_typeof(exclusions) = 'array'),
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    check (end_date >= start_date)
);

create table if not exists public.claims (
    claim_id text primary key,
    workflow_id text unique references public.workflows(workflow_id),
    claim_reference text unique,
    customer_id text references public.users(user_id),
    policy_id text references public.policies(policy_id),
    policy_number text,
    vehicle_registration text,
    incident_type text check (incident_type is null or incident_type in (
        'vehicle_collision', 'windscreen_damage', 'flood_damage', 'theft_or_break_in'
    )),
    incident_date date,
    incident_location text,
    incident_description text,
    damage_areas jsonb not null default '[]'::jsonb check (jsonb_typeof(damage_areas) = 'array'),
    claimed_amount numeric(14, 2) check (claimed_amount is null or claimed_amount >= 0),
    police_report_number text,
    claim_status text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now()
);

create table if not exists public.claim_documents (
    document_id text primary key,
    claim_id text not null references public.claims(claim_id),
    customer_id text not null references public.users(user_id),
    document_type text not null check (document_type in (
        'police_report', 'repair_estimate', 'claim_form', 'vehicle_registration',
        'damage_photo', 'identity_document', 'policy_document', 'invoice', 'photo',
        'policy_manual', 'procedure_guide', 'guideline', 'manual', 'other'
    )),
    file_name text,
    storage_reference text,
    incident_date date,
    claim_amount numeric(14, 2) check (claim_amount is null or claim_amount >= 0),
    incident_type text check (incident_type is null or incident_type in (
        'vehicle_collision', 'windscreen_damage', 'flood_damage', 'theft_or_break_in'
    )),
    police_report_number text,
    extracted_text text,
    document_facts jsonb not null default '{}'::jsonb check (jsonb_typeof(document_facts) = 'object'),
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default now()
);

create table if not exists public.fraud_assessments (
    assessment_id text primary key default gen_random_uuid()::text,
    claim_id text not null references public.claims(claim_id),
    risk_level text not null check (risk_level in ('low', 'medium', 'high')),
    risk_score double precision not null check (risk_score between 0 and 1),
    rule_score double precision not null check (rule_score between 0 and 1),
    anomaly_score double precision check (anomaly_score is null or anomaly_score between 0 and 1),
    indicators jsonb not null default '[]'::jsonb check (jsonb_typeof(indicators) = 'array'),
    missing_documents jsonb not null default '[]'::jsonb check (jsonb_typeof(missing_documents) = 'array'),
    recommended_action text not null check (recommended_action in (
        'continue_processing', 'request_documents', 'manual_review', 'escalate'
    )),
    automated_decision boolean not null default false check (automated_decision = false),
    rules_version text,
    model_version text,
    created_at timestamptz not null default now()
);

create table if not exists public.knowledge_chunks (
    chunk_id text primary key default gen_random_uuid()::text,
    source_document_id text not null,
    source_title text not null,
    insurance_type text not null default 'motor',
    document_type text check (document_type is null or document_type in (
        'police_report', 'repair_estimate', 'claim_form', 'vehicle_registration',
        'damage_photo', 'identity_document', 'policy_document', 'invoice', 'photo',
        'policy_manual', 'procedure_guide', 'guideline', 'manual', 'other'
    )),
    section text,
    content text not null check (length(btrim(content)) > 0),
    normalized_content text,
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object'),
    created_at timestamptz not null default now()
);

create table if not exists public.human_decisions (
    decision_id text primary key default gen_random_uuid()::text,
    workflow_id text references public.workflows(workflow_id),
    claim_id text references public.claims(claim_id),
    reviewer_id text not null references public.users(user_id),
    reviewer_role text check (reviewer_role is null or reviewer_role in ('claims_officer', 'admin')),
    decision text not null check (decision in (
        'approve', 'reject', 'request_more_information', 'escalate'
    )),
    notes text,
    reason text,
    requested_information jsonb not null default '[]'::jsonb check (jsonb_typeof(requested_information) = 'array'),
    settlement_amount numeric(14, 2) check (settlement_amount is null or settlement_amount >= 0),
    decided_at timestamptz,
    created_at timestamptz not null default now(),
    check (workflow_id is not null or claim_id is not null)
);

create index if not exists idx_workflows_authenticated_user_id on public.workflows(authenticated_user_id);
create index if not exists idx_workflows_current_status on public.workflows(current_status);
create index if not exists idx_workflows_created_at on public.workflows(created_at);
create index if not exists idx_policies_customer_id on public.policies(customer_id);
create index if not exists idx_policies_status on public.policies(status);
create index if not exists idx_claims_customer_id on public.claims(customer_id);
create index if not exists idx_claims_workflow_id on public.claims(workflow_id);
create index if not exists idx_claims_policy_id on public.claims(policy_id);
create index if not exists idx_claims_claim_status on public.claims(claim_status);
create index if not exists idx_claims_incident_type on public.claims(incident_type);
create index if not exists idx_claims_police_report_number on public.claims(police_report_number);
create index if not exists idx_claim_documents_claim_id on public.claim_documents(claim_id);
create index if not exists idx_claim_documents_customer_id on public.claim_documents(customer_id);
create index if not exists idx_fraud_assessments_claim_id on public.fraud_assessments(claim_id);
create index if not exists idx_knowledge_chunks_source_document_id on public.knowledge_chunks(source_document_id);
create index if not exists idx_knowledge_chunks_insurance_type on public.knowledge_chunks(insurance_type);
create index if not exists idx_knowledge_chunks_document_type on public.knowledge_chunks(document_type);
create index if not exists idx_human_decisions_workflow_id on public.human_decisions(workflow_id);
create index if not exists idx_human_decisions_claim_id on public.human_decisions(claim_id);
create index if not exists idx_human_decisions_reviewer_id on public.human_decisions(reviewer_id);
create unique index if not exists uq_human_decisions_workflow_id
on public.human_decisions(workflow_id) where workflow_id is not null;

create or replace function public.set_updated_at()
returns trigger language plpgsql as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

drop trigger if exists set_workflows_updated_at on public.workflows;
create trigger set_workflows_updated_at before update on public.workflows
for each row execute function public.set_updated_at();
drop trigger if exists set_policies_updated_at on public.policies;
create trigger set_policies_updated_at before update on public.policies
for each row execute function public.set_updated_at();
drop trigger if exists set_claims_updated_at on public.claims;
create trigger set_claims_updated_at before update on public.claims
for each row execute function public.set_updated_at();

create or replace function public.protect_workflow_identity()
returns trigger language plpgsql as $$
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
create trigger protect_workflow_identity_update before update on public.workflows
for each row execute function public.protect_workflow_identity();

-- Atomic authoritative human decision. Application callers use the service
-- role and still enforce claims-officer/admin authorization before this RPC.
create or replace function public.submit_human_review_decision(
    p_workflow_id text, p_claim_id text, p_expected_status text,
    p_target_status text, p_claim_status text, p_decision jsonb,
    p_human_review_result jsonb, p_audit_trail jsonb
) returns jsonb
language plpgsql security definer set search_path = public
as $$
declare current_workflow public.workflows%rowtype;
begin
    select * into current_workflow from public.workflows
    where workflow_id = p_workflow_id for update;
    if not found then raise exception 'workflow_not_found'; end if;
    if current_workflow.current_status <> p_expected_status then
        raise exception 'workflow_not_awaiting_review';
    end if;
    if exists (select 1 from public.human_decisions where workflow_id = p_workflow_id) then
        raise exception 'human_decision_already_exists';
    end if;
    if current_workflow.claim_context->>'claim_id' is distinct from p_claim_id then
        raise exception 'claim_workflow_mismatch';
    end if;

    insert into public.human_decisions (
        decision_id, workflow_id, claim_id, reviewer_id, reviewer_role,
        decision, reason, notes, requested_information, settlement_amount,
        decided_at, created_at
    ) values (
        p_decision->>'decision_id', p_workflow_id, p_claim_id,
        p_decision->>'reviewer_id', p_decision->>'reviewer_role',
        p_decision->>'decision', p_decision->>'reason', p_decision->>'notes',
        coalesce(p_decision->'requested_information', '[]'::jsonb),
        nullif(p_decision->>'settlement_amount', '')::numeric,
        (p_decision->>'decided_at')::timestamptz, now()
    );
    update public.claims set claim_status = p_claim_status, updated_at = now()
    where claim_id = p_claim_id;
    if not found then raise exception 'claim_not_found'; end if;
    update public.workflows
    set current_status = p_target_status,
        claim_context = jsonb_set(coalesce(claim_context, '{}'::jsonb),
            '{claim_status}', to_jsonb(p_claim_status), true),
        human_review_result = p_human_review_result,
        audit_trail = p_audit_trail,
        updated_at = now()
    where workflow_id = p_workflow_id;
    return p_decision;
end;
$$;

revoke all on function public.submit_human_review_decision(
    text, text, text, text, text, jsonb, jsonb, jsonb
) from public, anon, authenticated;
grant execute on function public.submit_human_review_decision(
    text, text, text, text, text, jsonb, jsonb, jsonb
) to service_role;
