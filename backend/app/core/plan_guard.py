from fastapi import HTTPException

from app.storage.repo import PlanLimitExceededError, enforce_plan_limits, get_plan_summary


def assert_plan_allows_access(user_id: str | None) -> None:
    try:
        enforce_plan_limits(user_id=user_id)
    except PlanLimitExceededError:
        plan = get_plan_summary(user_id=user_id)
        raise HTTPException(
            status_code=402,
            detail={
                "code": "PLAN_LIMIT_REACHED",
                "message": f"{plan.plan_name} limit reached. Upgrade to continue.",
                "plan": {
                    "name": plan.plan_name,
                    "code": plan.plan_code,
                    "status": plan.status,
                    "projects_used_this_month": plan.projects_used_this_month,
                    "monthly_project_limit": plan.monthly_project_limit,
                    "runs_used_this_month": plan.runs_used_this_month,
                    "monthly_run_limit": plan.monthly_run_limit,
                    "runs_per_project_limit": plan.runs_per_project_limit,
                    "idea_char_limit": plan.idea_char_limit,
                },
                "upgrade_hint": "Open /pricing to upgrade your plan.",
            },
        )
