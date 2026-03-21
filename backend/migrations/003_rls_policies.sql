alter table profiles enable row level security;
alter table projects enable row level security;
alter table specs enable row level security;
alter table pipeline_runs enable row level security;
alter table entities enable row level security;
alter table endpoints enable row level security;
alter table business_rules enable row level security;
alter table artifacts enable row level security;
alter table versions enable row level security;

-- Profiles: each user can see and edit only their own profile.
drop policy if exists profiles_select_own on profiles;
create policy profiles_select_own
on profiles
for select
using (id = auth.uid());

drop policy if exists profiles_insert_own on profiles;
create policy profiles_insert_own
on profiles
for insert
with check (id = auth.uid());

drop policy if exists profiles_update_own on profiles;
create policy profiles_update_own
on profiles
for update
using (id = auth.uid())
with check (id = auth.uid());

-- Core app tables: constrain by user_id.
drop policy if exists projects_all_own on projects;
create policy projects_all_own
on projects
for all
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists specs_all_own on specs;
create policy specs_all_own
on specs
for all
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists pipeline_runs_all_own on pipeline_runs;
create policy pipeline_runs_all_own
on pipeline_runs
for all
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists artifacts_all_own on artifacts;
create policy artifacts_all_own
on artifacts
for all
using (user_id = auth.uid())
with check (user_id = auth.uid());

drop policy if exists versions_all_own on versions;
create policy versions_all_own
on versions
for all
using (user_id = auth.uid())
with check (user_id = auth.uid());

-- Derived tables: access allowed only if parent pipeline_run belongs to auth.uid().
drop policy if exists entities_read_own on entities;
create policy entities_read_own
on entities
for select
using (
  exists (
    select 1
    from pipeline_runs pr
    where pr.id = entities.pipeline_run_id
      and pr.user_id = auth.uid()
  )
);

drop policy if exists endpoints_read_own on endpoints;
create policy endpoints_read_own
on endpoints
for select
using (
  exists (
    select 1
    from pipeline_runs pr
    where pr.id = endpoints.pipeline_run_id
      and pr.user_id = auth.uid()
  )
);

drop policy if exists business_rules_read_own on business_rules;
create policy business_rules_read_own
on business_rules
for select
using (
  exists (
    select 1
    from pipeline_runs pr
    where pr.id = business_rules.pipeline_run_id
      and pr.user_id = auth.uid()
  )
);

-- Supabase storage bucket for avatars (public read, owner write in own folder).
insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do nothing;

drop policy if exists avatars_public_read on storage.objects;
create policy avatars_public_read
on storage.objects
for select
using (bucket_id = 'avatars');

drop policy if exists avatars_insert_own_folder on storage.objects;
create policy avatars_insert_own_folder
on storage.objects
for insert
with check (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists avatars_update_own_folder on storage.objects;
create policy avatars_update_own_folder
on storage.objects
for update
using (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
)
with check (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
);

drop policy if exists avatars_delete_own_folder on storage.objects;
create policy avatars_delete_own_folder
on storage.objects
for delete
using (
  bucket_id = 'avatars'
  and (storage.foldername(name))[1] = auth.uid()::text
);
