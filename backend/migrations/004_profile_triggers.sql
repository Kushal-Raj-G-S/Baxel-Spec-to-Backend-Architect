-- Keep updated_at current for profile updates.
create or replace function public.set_current_timestamp_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at = now();
  return new;
end;
$$;

drop trigger if exists profiles_set_updated_at on public.profiles;
create trigger profiles_set_updated_at
before update on public.profiles
for each row
execute function public.set_current_timestamp_updated_at();

-- Derive a default username from email local-part.
create or replace function public.default_username_from_email(email_input text)
returns text
language sql
immutable
as $$
  select nullif(split_part(lower(coalesce(email_input, '')), '@', 1), '');
$$;

-- Create profile row automatically when a new auth user is created.
create or replace function public.handle_auth_user_created()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  metadata jsonb;
  derived_username text;
  derived_full_name text;
begin
  metadata := coalesce(new.raw_user_meta_data, '{}'::jsonb);
  derived_username := coalesce(
    nullif(trim(metadata ->> 'preferred_username'), ''),
    nullif(trim(metadata ->> 'user_name'), ''),
    nullif(trim(metadata ->> 'username'), ''),
    public.default_username_from_email(new.email)
  );
  derived_full_name := coalesce(
    nullif(trim(metadata ->> 'full_name'), ''),
    nullif(trim(metadata ->> 'name'), ''),
    nullif(trim(metadata ->> 'given_name'), '')
  );

  insert into public.profiles (id, email, username, full_name)
  values (new.id, new.email, derived_username, derived_full_name)
  on conflict (id) do update
    set email = excluded.email,
        username = coalesce(public.profiles.username, excluded.username),
        full_name = coalesce(public.profiles.full_name, excluded.full_name),
        updated_at = now();

  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
after insert on auth.users
for each row
execute function public.handle_auth_user_created();

-- Sync profile email/name details if auth user record is updated.
create or replace function public.handle_auth_user_updated()
returns trigger
language plpgsql
security definer
set search_path = public
as $$
declare
  metadata jsonb;
  incoming_full_name text;
begin
  metadata := coalesce(new.raw_user_meta_data, '{}'::jsonb);
  incoming_full_name := coalesce(
    nullif(trim(metadata ->> 'full_name'), ''),
    nullif(trim(metadata ->> 'name'), ''),
    nullif(trim(metadata ->> 'given_name'), '')
  );

  update public.profiles
  set email = new.email,
      full_name = coalesce(public.profiles.full_name, incoming_full_name),
      updated_at = now()
  where id = new.id;

  return new;
end;
$$;

drop trigger if exists on_auth_user_updated on auth.users;
create trigger on_auth_user_updated
after update of email, raw_user_meta_data on auth.users
for each row
execute function public.handle_auth_user_updated();

-- Backfill profiles for users created before triggers existed.
insert into public.profiles (id, email, username, full_name)
select
  u.id,
  u.email,
  coalesce(
    nullif(trim(u.raw_user_meta_data ->> 'preferred_username'), ''),
    nullif(trim(u.raw_user_meta_data ->> 'user_name'), ''),
    nullif(trim(u.raw_user_meta_data ->> 'username'), ''),
    public.default_username_from_email(u.email)
  ) as username,
  coalesce(
    nullif(trim(u.raw_user_meta_data ->> 'full_name'), ''),
    nullif(trim(u.raw_user_meta_data ->> 'name'), ''),
    nullif(trim(u.raw_user_meta_data ->> 'given_name'), '')
  ) as full_name
from auth.users u
on conflict (id) do update
set email = excluded.email,
    username = coalesce(public.profiles.username, excluded.username),
    full_name = coalesce(public.profiles.full_name, excluded.full_name),
    updated_at = now();
