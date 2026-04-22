create table if not exists pricing_plans (
  id uuid primary key default gen_random_uuid(),
  code text not null unique,
  display_name text not null,
  price_usd integer not null default 0,
  monthly_project_limit integer not null check (monthly_project_limit >= 0),
  monthly_run_limit integer not null check (monthly_run_limit >= 0),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

insert into pricing_plans (code, display_name, price_usd, monthly_project_limit, monthly_run_limit, is_active)
values
  ('starter', 'Starter', 0, 1, 3, true),
  ('creator', 'Creator', 12, 5, 20, true),
  ('studio', 'Studio', 24, 15, 75, true),
  ('growth', 'Growth', 79, 60, 300, true),
  ('enterprise', 'Enterprise', 249, 250, 100000, true)
on conflict (code) do update set
  display_name = excluded.display_name,
  price_usd = excluded.price_usd,
  monthly_project_limit = excluded.monthly_project_limit,
  monthly_run_limit = excluded.monthly_run_limit,
  is_active = excluded.is_active,
  updated_at = now();

alter table subscriptions
  add column if not exists plan_code text not null default 'starter',
  add column if not exists monthly_project_limit integer not null default 1;

update subscriptions
set plan_code = case lower(coalesce(plan_name, 'starter'))
  when 'starter' then 'starter'
  when 'studio' then 'studio'
  when 'scale' then 'growth'
  else 'starter'
end;

update subscriptions s
set
  plan_name = p.display_name,
  monthly_run_limit = p.monthly_run_limit,
  monthly_project_limit = p.monthly_project_limit,
  updated_at = now()
from pricing_plans p
where p.code = s.plan_code;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'fk_subscriptions_plan_code'
  ) then
    alter table subscriptions
      add constraint fk_subscriptions_plan_code
      foreign key (plan_code)
      references pricing_plans(code);
  end if;
end $$;

create table if not exists user_monthly_usage (
  id uuid primary key default gen_random_uuid(),
  user_id uuid not null references auth.users(id) on delete cascade,
  usage_month date not null,
  projects_created integer not null default 0,
  specs_created integer not null default 0,
  pipeline_runs integer not null default 0,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(user_id, usage_month)
);

create index if not exists idx_user_monthly_usage_user_month
  on user_monthly_usage(user_id, usage_month);

insert into user_monthly_usage (user_id, usage_month, projects_created, specs_created, pipeline_runs)
select
  agg.user_id,
  agg.usage_month,
  sum(agg.projects_created) as projects_created,
  sum(agg.specs_created) as specs_created,
  sum(agg.pipeline_runs) as pipeline_runs
from (
  select
    p.user_id,
    date_trunc('month', p.created_at)::date as usage_month,
    count(*)::integer as projects_created,
    0::integer as specs_created,
    0::integer as pipeline_runs
  from projects p
  where p.user_id is not null
  group by p.user_id, date_trunc('month', p.created_at)::date

  union all

  select
    s.user_id,
    date_trunc('month', s.created_at)::date as usage_month,
    0::integer as projects_created,
    count(*)::integer as specs_created,
    0::integer as pipeline_runs
  from specs s
  where s.user_id is not null
  group by s.user_id, date_trunc('month', s.created_at)::date

  union all

  select
    r.user_id,
    date_trunc('month', r.created_at)::date as usage_month,
    0::integer as projects_created,
    0::integer as specs_created,
    count(*)::integer as pipeline_runs
  from pipeline_runs r
  where r.user_id is not null
  group by r.user_id, date_trunc('month', r.created_at)::date
) agg
group by agg.user_id, agg.usage_month
on conflict (user_id, usage_month)
do update set
  projects_created = excluded.projects_created,
  specs_created = excluded.specs_created,
  pipeline_runs = excluded.pipeline_runs,
  updated_at = now();
