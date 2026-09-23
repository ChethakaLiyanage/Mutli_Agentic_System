-- Step 11: Add explicit policy_type category to policies table.
-- Supported policy categories: 'full_comprehensive', 'partial_comprehensive', 'third_party'.

alter table public.policies
    add column if not exists policy_type text;

-- Backfill policy_type from coverage_type where policy_type is not yet set
update public.policies
set policy_type =
    case
        when coverage_type = 'full' then 'full_comprehensive'
        when coverage_type = 'partial' then 'partial_comprehensive'
        when coverage_type = 'third_party' then 'third_party'
        else 'full_comprehensive'
    end
where policy_type is null;

-- Set default for new rows
alter table public.policies
    alter column policy_type set default 'full_comprehensive';

-- Add check constraint for supported policy categories
do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.policies'::regclass
          and conname = 'policies_policy_type_check'
    ) then
        alter table public.policies
            add constraint policies_policy_type_check
            check (policy_type in ('full_comprehensive', 'partial_comprehensive', 'third_party'));
    end if;
end;
$$;
