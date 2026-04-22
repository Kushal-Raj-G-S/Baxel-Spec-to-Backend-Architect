create table if not exists user_preferences (
  user_id uuid primary key references auth.users(id) on delete cascade,
  role text not null,
  intent text not null,
  experience text not null,
  created_at timestamptz not null default now()
);

create index if not exists idx_user_preferences_user_id on user_preferences(user_id);

alter table user_preferences enable row level security;

drop policy if exists user_preferences_select_own on user_preferences;
create policy user_preferences_select_own
on user_preferences
for select
using (user_id = auth.uid());

drop policy if exists user_preferences_insert_own on user_preferences;
create policy user_preferences_insert_own
on user_preferences
for insert
with check (user_id = auth.uid());

drop policy if exists user_preferences_update_own on user_preferences;
create policy user_preferences_update_own
on user_preferences
for update
using (user_id = auth.uid())
with check (user_id = auth.uid());
