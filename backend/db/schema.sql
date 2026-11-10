-- =====================================================================
-- Baxel – full Supabase schema (run once in the Supabase SQL editor)
-- Tables marked [ORIGINAL] were pasted from the old Supabase project.
-- Items marked [RECONSTRUCTED] were rebuilt from the application code
-- (not available from the old project) – review before relying on them.
-- =====================================================================

-- [RECONSTRUCTED] helper used by the profiles trigger
create or replace function public.set_current_timestamp_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

-- ---------------------------------------------------------------------
-- pricing_plans [ORIGINAL]
-- ---------------------------------------------------------------------
create table if not exists public.pricing_plans (
  id uuid not null default gen_random_uuid (),
  code text not null,
  display_name text not null,
  price_usd integer not null default 0,
  monthly_project_limit integer not null,
  monthly_run_limit integer not null,
  is_active boolean not null default true,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint pricing_plans_pkey primary key (id),
  constraint pricing_plans_code_key unique (code),
  constraint pricing_plans_monthly_project_limit_check check ((monthly_project_limit >= 0)),
  constraint pricing_plans_monthly_run_limit_check check ((monthly_run_limit >= 0))
) tablespace pg_default;

-- ---------------------------------------------------------------------
-- workspaces [ORIGINAL]
-- ---------------------------------------------------------------------
create table if not exists public.workspaces (
  id uuid not null default gen_random_uuid (),
  name text not null,
  owner_id uuid null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  constraint workspaces_pkey primary key (id)
) tablespace pg_default;

-- ---------------------------------------------------------------------
-- projects [ORIGINAL]
-- ---------------------------------------------------------------------
create table if not exists public.projects (
  id uuid not null default gen_random_uuid (),
  workspace_id uuid null,
  name text not null,
  description text null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  user_id uuid null,
  constraint projects_pkey primary key (id),
  constraint projects_user_id_fk foreign key (user_id) references auth.users (id) on delete set null,
  constraint projects_workspace_id_fkey foreign key (workspace_id) references workspaces (id) on delete set null
) tablespace pg_default;

create index if not exists idx_projects_workspace_id on public.projects using btree (workspace_id) tablespace pg_default;
create index if not exists idx_projects_user_id on public.projects using btree (user_id) tablespace pg_default;
create unique index if not exists idx_projects_user_id_name_unique on public.projects using btree (
  user_id,
  lower(trim(both from name))
) tablespace pg_default
where (user_id is not null);

-- ---------------------------------------------------------------------
-- specs [ORIGINAL]
-- ---------------------------------------------------------------------
create table if not exists public.specs (
  id uuid not null default gen_random_uuid (),
  project_id uuid not null,
  title text not null,
  content text not null,
  source_type text not null default 'paste'::text,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  user_id uuid null,
  constraint specs_pkey primary key (id),
  constraint specs_project_id_fkey foreign key (project_id) references projects (id) on delete cascade,
  constraint specs_user_id_fk foreign key (user_id) references auth.users (id) on delete set null
) tablespace pg_default;

create index if not exists idx_specs_project_id on public.specs using btree (project_id) tablespace pg_default;
create index if not exists idx_specs_user_id on public.specs using btree (user_id) tablespace pg_default;

-- ---------------------------------------------------------------------
-- pipeline_runs [RECONSTRUCTED from app/models/spec_db.py]
-- ---------------------------------------------------------------------
create table if not exists public.pipeline_runs (
  id uuid not null default gen_random_uuid (),
  project_id uuid not null,
  spec_id uuid null,
  status text not null,
  stages jsonb not null default '[]'::jsonb,
  result jsonb null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  completed_at timestamp with time zone null,
  user_id uuid null,
  constraint pipeline_runs_pkey primary key (id),
  constraint pipeline_runs_project_id_fkey foreign key (project_id) references projects (id) on delete cascade,
  constraint pipeline_runs_spec_id_fkey foreign key (spec_id) references specs (id) on delete set null,
  constraint pipeline_runs_user_id_fk foreign key (user_id) references auth.users (id) on delete set null
) tablespace pg_default;

create index if not exists idx_pipeline_runs_project_id on public.pipeline_runs using btree (project_id);
create index if not exists idx_pipeline_runs_spec_id on public.pipeline_runs using btree (spec_id);
create index if not exists idx_pipeline_runs_user_id on public.pipeline_runs using btree (user_id);

-- ---------------------------------------------------------------------
-- profiles [ORIGINAL]
-- ---------------------------------------------------------------------
create table if not exists public.profiles (
  id uuid not null,
  email text null,
  username text null,
  full_name text null,
  avatar_url text null,
  created_at timestamp with time zone not null default now(),
  updated_at timestamp with time zone not null default now(),
  plan_code text null default 'starter'::text,
  constraint profiles_pkey primary key (id),
  constraint profiles_username_key unique (username),
  constraint fk_profiles_plan_code foreign key (plan_code) references pricing_plans (code) on update cascade on delete set null,
  constraint profiles_auth_user_fk foreign key (id) references auth.users (id) on delete cascade
) tablespace pg_default;

create index if not exists idx_profiles_username on public.profiles using btree (username) tablespace pg_default;
create index if not exists idx_profiles_plan_code on public.profiles using btree (plan_code) tablespace pg_default;
create unique index if not exists profiles_username_unique_not_null on public.profiles using btree (username) tablespace pg_default
where ((username is not null) and (username <> ''::text));

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at before
update on public.profiles for each row
execute function set_current_timestamp_updated_at ();

-- ---------------------------------------------------------------------
-- user_preferences [ORIGINAL]
-- ---------------------------------------------------------------------
create table if not exists public.user_preferences (
  user_id uuid not null,
  role text not null,
  intent text not null,
  experience text not null,
  created_at timestamp with time zone not null default now(),
  heard_about text not null default 'other'::text,
  heard_about_other text null,
  constraint user_preferences_pkey primary key (user_id),
  constraint user_preferences_user_id_fkey foreign key (user_id) references auth.users (id) on delete cascade,
  constraint user_preferences_heard_about_check check (
    heard_about = any (array['linkedin'::text, 'product_hunt'::text, 'google'::text, 'other'::text])
  )
) tablespace pg_default;

create index if not exists idx_user_preferences_user_id on public.user_preferences using btree (user_id) tablespace pg_default;

-- ---------------------------------------------------------------------
-- chat_messages [ORIGINAL]
-- ---------------------------------------------------------------------
create table if not exists public.chat_messages (
  id character varying(36) not null,
  spec_id character varying(36) not null,
  user_id character varying(36) null,
  query text not null,
  response text not null,
  intent character varying(50) null,
  created_at timestamp without time zone not null,
  constraint chat_messages_pkey primary key (id)
) tablespace pg_default;

-- ---------------------------------------------------------------------
-- pricing_plans seed data [RECONSTRUCTED]
-- Limits come from backend/scratch/update_pricing_db.py. price_usd comes
-- from frontend/src/lib/pricing-plans.ts; legacy codes use the plan they map to.
-- Real enforcement lives in PLAN_LIMITS in dashboard_api.py; this table is
-- only a display override, but profiles.plan_code FKs to it, so every code
-- the app can assign must exist here.
-- ---------------------------------------------------------------------
insert into public.pricing_plans (code, display_name, price_usd, monthly_project_limit, monthly_run_limit) values
  ('starter',    'Starter',    0, 3,  9999),
  ('creator',    'Creator',    14, 7,  9999),
  ('studio',     'Studio',     45, 15, 9999),
  ('growth',     'Growth',     45, 30, 9999),
  ('enterprise', 'Enterprise', 0, 60, 9999),
  ('free',       'Free',       0, 3,  3),
  ('pro',        'Pro',        14, 15, 25),
  ('team',       'Team',       45, 50, 100)
on conflict (code) do nothing;

-- ---------------------------------------------------------------------
-- avatars storage bucket [RECONSTRUCTED]
-- Private bucket; the frontend uploads to "<user_id>/avatar-<ts>.<ext>"
-- and reads through signed URLs.
-- ---------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', false)
on conflict (id) do nothing;

drop policy if exists "avatars_select_own" on storage.objects;
drop policy if exists "avatars_insert_own" on storage.objects;
drop policy if exists "avatars_update_own" on storage.objects;
drop policy if exists "avatars_delete_own" on storage.objects;

create policy "avatars_select_own" on storage.objects for select to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "avatars_insert_own" on storage.objects for insert to authenticated
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "avatars_update_own" on storage.objects for update to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
create policy "avatars_delete_own" on storage.objects for delete to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);

-- ---------------------------------------------------------------------
-- Row level security [RECONSTRUCTED]
-- The FastAPI backend connects with the database owner role (bypasses RLS).
-- The browser only touches user_preferences and the avatars bucket directly,
-- so RLS is enabled everywhere and only user_preferences gets policies.
-- ---------------------------------------------------------------------
alter table public.user_preferences enable row level security;
drop policy if exists "user_preferences_own" on public.user_preferences;
create policy "user_preferences_own" on public.user_preferences for all to authenticated
  using (user_id = auth.uid()) with check (user_id = auth.uid());

alter table public.pricing_plans  enable row level security;
alter table public.workspaces     enable row level security;
alter table public.projects       enable row level security;
alter table public.specs          enable row level security;
alter table public.pipeline_runs  enable row level security;
alter table public.profiles       enable row level security;
alter table public.chat_messages  enable row level security;
