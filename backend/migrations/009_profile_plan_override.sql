alter table profiles
  add column if not exists plan_code text;

update profiles
set plan_code = lower(trim(plan_code))
where plan_code is not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'fk_profiles_plan_code'
  ) then
    alter table profiles
      add constraint fk_profiles_plan_code
      foreign key (plan_code)
      references pricing_plans(code)
      on update cascade
      on delete set null;
  end if;
end $$;

create index if not exists idx_profiles_plan_code on profiles(plan_code);
