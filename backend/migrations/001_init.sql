create extension if not exists pgcrypto;

create table if not exists workspaces (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  owner_id uuid,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists projects (
  id uuid primary key default gen_random_uuid(),
  workspace_id uuid references workspaces(id) on delete set null,
  name text not null,
  description text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists project_members (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  user_id uuid not null,
  role text not null default 'owner',
  created_at timestamptz not null default now(),
  unique (project_id, user_id)
);

create table if not exists specs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  title text not null,
  content text not null,
  source_type text not null default 'paste',
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists pipeline_runs (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  spec_id uuid references specs(id) on delete set null,
  status text not null,
  stages jsonb not null default '[]'::jsonb,
  result jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  completed_at timestamptz
);

create table if not exists entities (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null references pipeline_runs(id) on delete cascade,
  name text not null,
  fields jsonb,
  created_at timestamptz not null default now()
);

create table if not exists endpoints (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null references pipeline_runs(id) on delete cascade,
  method text not null,
  path text not null,
  description text,
  request_schema jsonb,
  response_schema jsonb,
  created_at timestamptz not null default now()
);

create table if not exists business_rules (
  id uuid primary key default gen_random_uuid(),
  pipeline_run_id uuid not null references pipeline_runs(id) on delete cascade,
  rule_text text not null,
  created_at timestamptz not null default now()
);

create table if not exists artifacts (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  pipeline_run_id uuid references pipeline_runs(id) on delete set null,
  stack text,
  artifact_url text,
  created_at timestamptz not null default now()
);

create table if not exists versions (
  id uuid primary key default gen_random_uuid(),
  project_id uuid not null references projects(id) on delete cascade,
  spec_id uuid references specs(id) on delete set null,
  pipeline_run_id uuid references pipeline_runs(id) on delete set null,
  arch_hash text,
  created_at timestamptz not null default now()
);

create index if not exists idx_projects_workspace_id on projects(workspace_id);
create index if not exists idx_specs_project_id on specs(project_id);
create index if not exists idx_pipeline_runs_project_id on pipeline_runs(project_id);
create index if not exists idx_pipeline_runs_spec_id on pipeline_runs(spec_id);
create index if not exists idx_entities_pipeline_run_id on entities(pipeline_run_id);
create index if not exists idx_endpoints_pipeline_run_id on endpoints(pipeline_run_id);
create index if not exists idx_rules_pipeline_run_id on business_rules(pipeline_run_id);
create index if not exists idx_artifacts_project_id on artifacts(project_id);
