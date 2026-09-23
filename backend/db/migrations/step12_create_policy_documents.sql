-- Step 12: Create policy_documents table for controlled knowledge base versioning and management.
-- Supports: 'processing', 'active', 'superseded', 'failed', 'archived' statuses.

create table if not exists public.policy_documents (
    id text primary key default gen_random_uuid()::text,
    root_document_id text not null,
    title text not null,
    document_type text not null check (document_type in (
        'policy_document', 'policy_manual', 'procedure_guide', 'guideline', 'manual', 'other'
    )),
    policy_type text check (policy_type is null or policy_type in (
        'full_comprehensive', 'partial_comprehensive', 'third_party'
    )),
    audience text not null default 'customer' check (audience in ('customer', 'internal', 'all')),
    version text not null default '1.0',
    original_filename text not null,
    storage_path text,
    checksum text,
    status text not null default 'active' check (status in (
        'processing', 'active', 'superseded', 'failed', 'archived'
    )),
    chunks_count integer not null default 0 check (chunks_count >= 0),
    previous_version_id text references public.policy_documents(id),
    change_summary text,
    uploaded_by text default 'admin',
    created_at timestamptz not null default now(),
    activated_at timestamptz,
    superseded_at timestamptz,
    updated_at timestamptz not null default now(),
    metadata jsonb not null default '{}'::jsonb check (jsonb_typeof(metadata) = 'object')
);

create index if not exists idx_policy_documents_status on public.policy_documents(status);
create index if not exists idx_policy_documents_root_id on public.policy_documents(root_document_id);
create index if not exists idx_policy_documents_policy_type on public.policy_documents(policy_type);
create index if not exists idx_policy_documents_document_type on public.policy_documents(document_type);
create index if not exists idx_policy_documents_audience on public.policy_documents(audience);
