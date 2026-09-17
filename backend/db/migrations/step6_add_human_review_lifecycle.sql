-- Step 6: authoritative human-review lifecycle.
-- Preserves all existing workflows, claims, assessments, and decisions.

alter table public.human_decisions
    add column if not exists reviewer_role text;

alter table public.human_decisions
    add column if not exists reason text;

alter table public.human_decisions
    drop constraint if exists human_decisions_reviewer_role_check;

alter table public.human_decisions
    add constraint human_decisions_reviewer_role_check
    check (reviewer_role is null or reviewer_role in ('claims_officer', 'admin'));

create unique index if not exists uq_human_decisions_workflow_id
    on public.human_decisions(workflow_id)
    where workflow_id is not null;

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
        'guidance_processing', 'completed', 'failed'
    ));

create or replace function public.submit_human_review_decision(
    p_workflow_id text,
    p_claim_id text,
    p_expected_status text,
    p_target_status text,
    p_claim_status text,
    p_decision jsonb,
    p_human_review_result jsonb,
    p_audit_trail jsonb
) returns jsonb
language plpgsql
security definer
set search_path = public
as $$
declare
    current_workflow public.workflows%rowtype;
begin
    select * into current_workflow
    from public.workflows
    where workflow_id = p_workflow_id
    for update;

    if not found then
        raise exception 'workflow_not_found';
    end if;
    if current_workflow.current_status <> p_expected_status then
        raise exception 'workflow_not_awaiting_review';
    end if;
    if exists (
        select 1 from public.human_decisions
        where workflow_id = p_workflow_id
    ) then
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

    update public.claims
    set claim_status = p_claim_status, updated_at = now()
    where claim_id = p_claim_id;
    if not found then
        raise exception 'claim_not_found';
    end if;

    update public.workflows
    set current_status = p_target_status,
        claim_context = jsonb_set(
            coalesce(claim_context, '{}'::jsonb),
            '{claim_status}', to_jsonb(p_claim_status), true
        ),
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
