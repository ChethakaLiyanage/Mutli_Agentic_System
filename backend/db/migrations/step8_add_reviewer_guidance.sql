alter table if exists public.workflows
    add column if not exists reviewer_guidance_result jsonb;