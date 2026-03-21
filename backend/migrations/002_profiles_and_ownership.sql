create table if not exists profiles (
  id uuid primary key,
  email text,
  username text unique,
  full_name text,
  avatar_url text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint profiles_auth_user_fk
    foreign key (id)
    references auth.users(id)
    on delete cascade
);

alter table projects add column if not exists user_id uuid;
alter table specs add column if not exists user_id uuid;
alter table pipeline_runs add column if not exists user_id uuid;
alter table artifacts add column if not exists user_id uuid;
alter table versions add column if not exists user_id uuid;

do $$
begin
  if not exists (select 1 from pg_constraint where conname = 'projects_user_id_fk') then
    alter table projects
      add constraint projects_user_id_fk
      foreign key (user_id)
      references auth.users(id)
      on delete set null;
  end if;

  if not exists (select 1 from pg_constraint where conname = 'specs_user_id_fk') then
    alter table specs
      add constraint specs_user_id_fk
      foreign key (user_id)
      references auth.users(id)
      on delete set null;
  end if;

  if not exists (select 1 from pg_constraint where conname = 'pipeline_runs_user_id_fk') then
    alter table pipeline_runs
      add constraint pipeline_runs_user_id_fk
      foreign key (user_id)
      references auth.users(id)
      on delete set null;
  end if;

  if not exists (select 1 from pg_constraint where conname = 'artifacts_user_id_fk') then
    alter table artifacts
      add constraint artifacts_user_id_fk
      foreign key (user_id)
      references auth.users(id)
      on delete set null;
  end if;

  if not exists (select 1 from pg_constraint where conname = 'versions_user_id_fk') then
    alter table versions
      add constraint versions_user_id_fk
      foreign key (user_id)
      references auth.users(id)
      on delete set null;
  end if;
end
$$;

create index if not exists idx_projects_user_id on projects(user_id);
create index if not exists idx_specs_user_id on specs(user_id);
create index if not exists idx_pipeline_runs_user_id on pipeline_runs(user_id);
create index if not exists idx_profiles_username on profiles(username);
