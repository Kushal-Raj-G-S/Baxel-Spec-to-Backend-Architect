-- Collapse duplicate project names per user, then enforce uniqueness for future inserts.
with ranked_projects as (
  select
    id,
    user_id,
    lower(trim(name)) as normalized_name,
    created_at,
    first_value(id) over (
      partition by user_id, lower(trim(name))
      order by created_at asc
    ) as canonical_id,
    row_number() over (
      partition by user_id, lower(trim(name))
      order by created_at asc
    ) as row_num
  from projects
  where user_id is not null
), duplicate_projects as (
  select id, canonical_id
  from ranked_projects
  where row_num > 1
)
update specs s
set project_id = d.canonical_id
from duplicate_projects d
where s.project_id = d.id;

with ranked_projects as (
  select
    id,
    user_id,
    lower(trim(name)) as normalized_name,
    created_at,
    first_value(id) over (
      partition by user_id, lower(trim(name))
      order by created_at asc
    ) as canonical_id,
    row_number() over (
      partition by user_id, lower(trim(name))
      order by created_at asc
    ) as row_num
  from projects
  where user_id is not null
), duplicate_projects as (
  select id, canonical_id
  from ranked_projects
  where row_num > 1
)
update pipeline_runs p
set project_id = d.canonical_id
from duplicate_projects d
where p.project_id = d.id;

with ranked_projects as (
  select
    id,
    user_id,
    lower(trim(name)) as normalized_name,
    created_at,
    row_number() over (
      partition by user_id, lower(trim(name))
      order by created_at asc
    ) as row_num
  from projects
  where user_id is not null
)
delete from projects p
using ranked_projects r
where p.id = r.id
  and r.row_num > 1;

create unique index if not exists idx_projects_user_id_name_unique
  on projects(user_id, lower(trim(name)))
  where user_id is not null;

create table if not exists subscriptions (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  plan_name text not null default 'Starter',
  status text not null default 'active',
  monthly_run_limit integer not null default 3,
  period_start timestamptz,
  period_end timestamptz,
  manage_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index if not exists idx_subscriptions_user_id on subscriptions(user_id);
