alter table user_preferences
  add column if not exists heard_about text,
  add column if not exists heard_about_other text;

update user_preferences
set heard_about = 'other'
where heard_about is null;

alter table user_preferences
  alter column heard_about set default 'other';

alter table user_preferences
  alter column heard_about set not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'user_preferences_heard_about_check'
  ) then
    alter table user_preferences
      add constraint user_preferences_heard_about_check
      check (heard_about in ('linkedin', 'product_hunt', 'google', 'other'));
  end if;
end
$$;
