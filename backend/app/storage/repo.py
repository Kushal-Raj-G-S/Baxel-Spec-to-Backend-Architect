from app.core.config import settings
from app.storage import memory, supabase
from app.schemas import (
    DashboardSummary,
    PlanSummary,
    ProjectHistory,
    PublicMetrics,
    PipelineRunListItem,
    SharedRunResponse,
    ShareTokenResponse,
    PipelineStatus,
    ProfileResponse,
    ProfileUpdate,
    Project,
    ProjectCreate,
    Spec,
    SpecCreate,
)


class PlanLimitExceededError(RuntimeError):
    pass


def _use_supabase() -> bool:
    return bool(settings.supabase_url and settings.supabase_service_role_key)


def create_project(payload: ProjectCreate, user_id: str | None = None) -> Project:
    if _use_supabase():
        return supabase.create_project(payload, user_id=user_id)
    return memory.create_project(payload, user_id=user_id)


def list_projects(user_id: str | None = None):
    if _use_supabase():
        return supabase.list_projects(user_id=user_id)
    return memory.list_projects(user_id=user_id)


def get_project(project_id: str, user_id: str | None = None) -> Project | None:
    if _use_supabase():
        return supabase.get_project(project_id, user_id=user_id)
    return memory.get_project(project_id, user_id=user_id)


def get_project_history(project_id: str, user_id: str | None = None) -> ProjectHistory | None:
    if _use_supabase():
        return supabase.get_project_history(project_id, user_id=user_id)
    return memory.get_project_history(project_id, user_id=user_id)


def list_projects_history(user_id: str | None = None, limit: int = 100) -> list[ProjectHistory]:
    if _use_supabase():
        return supabase.list_projects_history(user_id=user_id, limit=limit)
    return memory.list_projects_history(user_id=user_id, limit=limit)


def create_spec(payload: SpecCreate, user_id: str | None = None) -> Spec:
    if _use_supabase():
        return supabase.create_spec(payload, user_id=user_id)
    return memory.create_spec(payload, user_id=user_id)


def list_specs(project_id: str, user_id: str | None = None):
    if _use_supabase():
        return supabase.list_specs(project_id, user_id=user_id)
    return memory.list_specs(project_id, user_id=user_id)


def get_spec(spec_id: str, user_id: str | None = None) -> Spec | None:
    if _use_supabase():
        return supabase.get_spec(spec_id, user_id=user_id)
    return memory.get_spec(spec_id, user_id=user_id)


def create_pipeline(
    status: PipelineStatus,
    project_id: str | None = None,
    spec_id: str | None = None,
    user_id: str | None = None,
) -> PipelineStatus:
    if _use_supabase():
        return supabase.create_pipeline(status, project_id=project_id, spec_id=spec_id, user_id=user_id)
    return memory.create_pipeline(status, project_id=project_id, spec_id=spec_id, user_id=user_id)


def update_pipeline(status: PipelineStatus) -> PipelineStatus:
    if _use_supabase():
        return supabase.update_pipeline(status)
    return memory.update_pipeline(status)


def get_pipeline(pipeline_id: str, user_id: str | None = None) -> PipelineStatus | None:
    if _use_supabase():
        return supabase.get_pipeline(pipeline_id, user_id=user_id)
    return memory.get_pipeline(pipeline_id, user_id=user_id)


def list_pipeline_runs(user_id: str | None = None, limit: int = 50) -> list[PipelineRunListItem]:
    if _use_supabase():
        return supabase.list_pipeline_runs(user_id=user_id, limit=limit)
    return memory.list_pipeline_runs(user_id=user_id, limit=limit)


def store_pipeline_outputs(pipeline_id: str, outputs: dict) -> None:
    if _use_supabase():
        supabase.store_pipeline_outputs(pipeline_id, outputs)
        return None
    return memory.store_pipeline_outputs(pipeline_id, outputs)


def get_dashboard_summary(user_id: str | None = None) -> DashboardSummary:
    if _use_supabase():
        return supabase.get_dashboard_summary(user_id=user_id)
    return memory.get_dashboard_summary(user_id=user_id)


def get_public_metrics() -> PublicMetrics:
    if _use_supabase():
        return supabase.get_public_metrics()
    return memory.get_public_metrics()


def get_plan_summary(user_id: str | None = None) -> PlanSummary:
    if _use_supabase():
        return supabase.get_plan_summary(user_id=user_id)
    return memory.get_plan_summary(user_id=user_id)


def enforce_plan_limits(user_id: str | None = None) -> None:
    if not user_id:
        return

    plan = get_plan_summary(user_id=user_id)
    status = (plan.status or "active").lower()
    project_limit_hit = plan.monthly_project_limit >= 0 and plan.projects_used_this_month >= plan.monthly_project_limit
    run_limit_hit = plan.monthly_run_limit >= 0 and plan.runs_used_this_month >= plan.monthly_run_limit
    if status != "active" or project_limit_hit or run_limit_hit:
        raise PlanLimitExceededError(
            f"Plan limit reached for {plan.plan_name}: "
            f"projects {plan.projects_used_this_month}/{plan.monthly_project_limit}, "
            f"runs {plan.runs_used_this_month}/{plan.monthly_run_limit}. Upgrade required."
        )


def enforce_project_creation_limit(user_id: str | None = None) -> None:
    if not user_id:
        return

    plan = get_plan_summary(user_id=user_id)
    status = (plan.status or "active").lower()
    project_limit_hit = plan.monthly_project_limit >= 0 and plan.projects_used_this_month >= plan.monthly_project_limit
    if status != "active" or project_limit_hit:
        raise PlanLimitExceededError(
            f"Project limit reached for {plan.plan_name}: "
            f"projects {plan.projects_used_this_month}/{plan.monthly_project_limit}. "
            "Upgrade required."
        )


def enforce_project_pipeline_limit(project_id: str | None, user_id: str | None = None) -> None:
    if not user_id or not project_id:
        return

    if _use_supabase():
        return supabase.enforce_project_pipeline_limit(project_id=project_id, user_id=user_id)
    return memory.enforce_project_pipeline_limit(project_id=project_id, user_id=user_id)


def create_share_token(run_id: str, user_id: str | None = None) -> ShareTokenResponse | None:
    if _use_supabase():
        return supabase.create_share_token(run_id=run_id, user_id=user_id)
    return memory.create_share_token(run_id=run_id, user_id=user_id)


def get_shared_run_by_token(token: str) -> SharedRunResponse | None:
    if _use_supabase():
        return supabase.get_shared_run_by_token(token)
    return memory.get_shared_run_by_token(token)


def get_profile(user_id: str, email: str | None = None) -> ProfileResponse:
    if _use_supabase():
        return supabase.get_profile(user_id=user_id, email=email)
    return memory.get_profile(user_id=user_id, email=email)


def update_profile(user_id: str, payload: ProfileUpdate, email: str | None = None) -> ProfileResponse:
    if _use_supabase():
        return supabase.update_profile(user_id=user_id, payload=payload, email=email)
    return memory.update_profile(user_id=user_id, payload=payload, email=email)
