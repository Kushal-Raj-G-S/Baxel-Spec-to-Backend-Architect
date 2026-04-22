update pricing_plans
set
  display_name = 'Starter',
  price_usd = 0,
  monthly_project_limit = 3,
  monthly_run_limit = 9,
  is_active = true,
  updated_at = now()
where code = 'starter';

update pricing_plans
set
  display_name = 'Creator',
  price_usd = 8,
  monthly_project_limit = 7,
  monthly_run_limit = 25,
  is_active = true,
  updated_at = now()
where code = 'creator';

update pricing_plans
set
  display_name = 'Studio',
  price_usd = 20,
  monthly_project_limit = 15,
  monthly_run_limit = 75,
  is_active = true,
  updated_at = now()
where code = 'studio';

update pricing_plans
set
  display_name = 'Growth',
  price_usd = 50,
  is_active = true,
  updated_at = now()
where code = 'growth';

update pricing_plans
set
  display_name = 'Enterprise',
  price_usd = 158,
  is_active = true,
  updated_at = now()
where code = 'enterprise';

alter table subscriptions
  alter column plan_code set default 'starter',
  alter column plan_name set default 'Starter',
  alter column monthly_project_limit set default 3,
  alter column monthly_run_limit set default 9;

update subscriptions s
set
  plan_name = p.display_name,
  monthly_project_limit = p.monthly_project_limit,
  monthly_run_limit = p.monthly_run_limit,
  updated_at = now()
from pricing_plans p
where p.code = s.plan_code;
