update profiles
set plan_code = 'starter',
    updated_at = now()
where plan_code is null
   or trim(plan_code) = '';

alter table profiles
  alter column plan_code set default 'starter';
