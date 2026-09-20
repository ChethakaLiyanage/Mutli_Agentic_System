-- Step 10: Add explicit motor coverage types and seed customer policies.
-- The four customer accounts must already exist before this migration runs.

alter table public.policies
    add column if not exists coverage_type text not null default 'full';

do $$
begin
    if not exists (
        select 1
        from pg_constraint
        where conrelid = 'public.policies'::regclass
          and conname = 'policies_coverage_type_check'
    ) then
        alter table public.policies
            add constraint policies_coverage_type_check
            check (coverage_type in ('full', 'partial', 'third_party'));
    end if;
end;
$$;

do $$
begin
    if (
        select count(*)
        from public.users
        where lower(email) in (
            'binu@gmail.com',
            'adithya@gmail.com',
            'chethaka@gmail.com',
            'chathurya@gmail.com'
        )
    ) <> 4 then
        raise exception 'All four customer accounts must exist before seeding motor policies';
    end if;
end;
$$;

insert into public.policies (
    policy_id,
    policy_number,
    customer_id,
    insurance_type,
    coverage_type,
    status,
    start_date,
    end_date,
    coverage_details,
    exclusions
)
select
    seed.policy_id,
    seed.policy_number,
    users.user_id,
    'motor',
    seed.coverage_type,
    'active',
    seed.start_date,
    seed.end_date,
    seed.coverage_details,
    seed.exclusions
from (
    values
        (
            'POL-BINU-2026', 'MTR-BINU-2026', 'binu@gmail.com', 'full',
            date '2026-01-01', date '2026-12-31',
            '{"own_damage": true, "third_party_liability": true, "theft": true, "fire": true, "flood": true, "windscreen": true, "personal_accident": true, "deductible": 250, "coverage_limit": 500000}'::jsonb,
            '["racing", "intentional damage", "driving without a valid licence"]'::jsonb
        ),
        (
            'POL-ADITHYA-2026', 'MTR-ADITHYA-2026', 'adithya@gmail.com', 'partial',
            date '2026-02-01', date '2027-01-31',
            '{"own_damage": true, "third_party_liability": true, "theft": true, "fire": false, "flood": false, "windscreen": false, "personal_accident": false, "deductible": 500, "coverage_limit": 300000}'::jsonb,
            '["flood and water damage", "windscreen-only damage", "racing"]'::jsonb
        ),
        (
            'POL-CHETHAKA-2026', 'MTR-CHETHAKA-2026', 'chethaka@gmail.com', 'third_party',
            date '2026-03-01', date '2027-02-28',
            '{"own_damage": false, "third_party_liability": true, "theft": false, "fire": false, "flood": false, "windscreen": false, "personal_accident": false, "deductible": 0, "coverage_limit": 1000000}'::jsonb,
            '["damage to the insured vehicle", "theft", "fire", "flood"]'::jsonb
        ),
        (
            'POL-CHATHURYA-2026', 'MTR-CHATHURYA-2026', 'chathurya@gmail.com', 'full',
            date '2026-04-01', date '2027-03-31',
            '{"own_damage": true, "third_party_liability": true, "theft": true, "fire": true, "flood": false, "windscreen": true, "personal_accident": true, "deductible": 350, "coverage_limit": 750000}'::jsonb,
            '["racing", "commercial use without endorsement", "intentional damage"]'::jsonb
        )
) as seed(
    policy_id, policy_number, email, coverage_type,
    start_date, end_date, coverage_details, exclusions
)
join public.users on lower(public.users.email) = seed.email
on conflict (policy_id) do update set
    policy_number = excluded.policy_number,
    customer_id = excluded.customer_id,
    insurance_type = excluded.insurance_type,
    coverage_type = excluded.coverage_type,
    status = excluded.status,
    start_date = excluded.start_date,
    end_date = excluded.end_date,
    coverage_details = excluded.coverage_details,
    exclusions = excluded.exclusions,
    updated_at = now();
