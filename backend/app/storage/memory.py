from datetime import datetime
from typing import Dict, List
import uuid
import base64
import hashlib
import hmac
import json

from app.schemas import (
        ProfileResponse,
        ProfileUpdate,
    DashboardPipelineItem,
    DashboardProjectItem,
    DashboardSummary,
    PlanSummary,
    PipelineRunListItem,
    ProjectHistory,
    ProjectHistoryRunItem,
    PublicMetrics,
    SharedRunResponse,
    ShareTokenResponse,
    PipelineStatus,
    Project,
    ProjectCreate,
    Spec,
    SpecCreate,
)

_projects: Dict[str, Project] = {}
_specs: Dict[str, Spec] = {}
_pipelines: Dict[str, PipelineStatus] = {}
_pipeline_project_map: Dict[str, str] = {}
_pipeline_spec_map: Dict[str, str] = {}
_pipeline_created_at: Dict[str, datetime] = {}
_profiles: Dict[str, ProfileResponse] = {}
_share_secret = "baxel-memory-share-secret"


def _sign_share_payload(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    signature = hmac.new(_share_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _verify_share_token(token: str) -> dict | None:
    if "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    expected = hmac.new(_share_secret.encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode((encoded + padding).encode("utf-8")).decode("utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def create_project(payload: ProjectCreate, user_id: str | None = None) -> Project:
    normalized_name = (payload.name or "").strip().lower()
    for existing in _projects.values():
        if existing.name.strip().lower() == normalized_name:
            if payload.description and payload.description != existing.description:
                existing.description = payload.description
            return existing

    project_id = str(uuid.uuid4())
    project = Project(id=project_id, created_at=datetime.utcnow(), **payload.model_dump())
    _projects[project_id] = project
    return project


def list_projects(user_id: str | None = None) -> List[Project]:
    return list(_projects.values())


def get_project(project_id: str, user_id: str | None = None) -> Project | None:
    return _projects.get(project_id)


def get_project_history(project_id: str, user_id: str | None = None) -> ProjectHistory | None:
    project = _projects.get(project_id)
    if not project:
        return None

    specs = [spec for spec in _specs.values() if spec.project_id == project_id]
    spec_lookup = {spec.id: spec.title for spec in specs}

    project_runs = [
        pipeline
        for pipeline in _pipelines.values()
        if _pipeline_project_map.get(pipeline.id) == project_id
    ]

    project_runs.sort(key=lambda item: _pipeline_created_at.get(item.id, datetime.utcnow()), reverse=True)

    recent_runs = [
        ProjectHistoryRunItem(
            id=item.id,
            status=item.status,
            created_at=_pipeline_created_at.get(item.id) or datetime.utcnow(),
            spec_id=_pipeline_spec_map.get(item.id),
            spec_title=spec_lookup.get(_pipeline_spec_map.get(item.id)),
            result=item.result,
        )
        for item in project_runs[:10]
    ]

    return ProjectHistory(
        project=project,
        specs_count=len(specs),
        pipeline_runs_count=len(project_runs),
        recent_runs=recent_runs,
    )


def list_projects_history(user_id: str | None = None, limit: int = 100) -> List[ProjectHistory]:
    histories: List[ProjectHistory] = []
    for project in list(_projects.values())[:limit]:
        history = get_project_history(project.id, user_id=user_id)
        if history:
            histories.append(history)
    return histories


def create_spec(payload: SpecCreate, user_id: str | None = None) -> Spec:
    spec_id = str(uuid.uuid4())
    spec = Spec(id=spec_id, created_at=datetime.utcnow(), **payload.model_dump())
    _specs[spec_id] = spec
    return spec


def list_specs(project_id: str, user_id: str | None = None) -> List[Spec]:
    return [spec for spec in _specs.values() if spec.project_id == project_id]


def get_spec(spec_id: str, user_id: str | None = None) -> Spec | None:
    return _specs.get(spec_id)


def create_pipeline(
    status: PipelineStatus,
    project_id: str | None = None,
    spec_id: str | None = None,
    user_id: str | None = None,
) -> PipelineStatus:
    _pipelines[status.id] = status
    if project_id:
        _pipeline_project_map[status.id] = project_id
    if spec_id:
        _pipeline_spec_map[status.id] = spec_id
    _pipeline_created_at[status.id] = datetime.utcnow()
    return status


def update_pipeline(status: PipelineStatus) -> PipelineStatus:
    _pipelines[status.id] = status
    return status


def get_pipeline(pipeline_id: str, user_id: str | None = None) -> PipelineStatus | None:
    return _pipelines.get(pipeline_id)


def list_pipeline_runs(user_id: str | None = None, limit: int = 50) -> List[PipelineRunListItem]:
    pipeline_items = sorted(
        _pipelines.values(),
        key=lambda item: _pipeline_created_at.get(item.id, datetime.utcnow()),
        reverse=True,
    )[:limit]

    response: List[PipelineRunListItem] = []
    for item in pipeline_items:
        project_id = _pipeline_project_map.get(item.id)
        spec_id = _pipeline_spec_map.get(item.id)
        response.append(
            PipelineRunListItem(
                id=item.id,
                status=item.status,
                created_at=_pipeline_created_at.get(item.id) or datetime.utcnow(),
                completed_at=_pipeline_created_at.get(item.id) if item.status.lower() == "completed" else None,
                project_name=_projects.get(project_id).name if project_id and _projects.get(project_id) else None,
                spec_title=_specs.get(spec_id).title if spec_id and _specs.get(spec_id) else None,
                duration_seconds=0 if item.status.lower() == "completed" else None,
            )
        )

    return response


def store_pipeline_outputs(pipeline_id: str, outputs: dict) -> None:
    return None


def get_dashboard_summary(user_id: str | None = None) -> DashboardSummary:
    recent_projects = sorted(_projects.values(), key=lambda item: item.created_at, reverse=True)[:5]
    recent_pipelines = sorted(_pipelines.values(), key=lambda item: item.id, reverse=True)[:5]

    return DashboardSummary(
        projects_count=len(_projects),
        specs_count=len(_specs),
        pipeline_runs_count=len(_pipelines),
        recent_projects=[
            DashboardProjectItem(id=item.id, name=item.name, created_at=item.created_at)
            for item in recent_projects
        ],
        recent_pipeline_runs=[
            DashboardPipelineItem(
                id=item.id,
                status=item.status,
                created_at=datetime.utcnow(),
            )
            for item in recent_pipelines
        ],
    )


def get_public_metrics() -> PublicMetrics:
    return PublicMetrics(
        specs_processed=len(_specs),
        schemas_generated=len(_pipelines),
        api_endpoints=0,
        rules_captured=0,
    )


def get_plan_summary(user_id: str | None = None) -> PlanSummary:
    now = datetime.utcnow()
    return PlanSummary(
        plan_name="Starter",
        status="active",
        monthly_run_limit=3,
        runs_used_this_month=len(_pipelines),
        billing_period=f"{now.date().isoformat()} to {now.date().isoformat()}",
        period_start=now,
        period_end=now,
        manage_url=None,
    )


def create_share_token(run_id: str, user_id: str | None = None) -> ShareTokenResponse | None:
    run = _pipelines.get(run_id)
    if not run:
        return None
    return ShareTokenResponse(
        token=_sign_share_payload({"run_id": run_id, "issued_at": datetime.utcnow().isoformat()})
    )


def get_shared_run_by_token(token: str) -> SharedRunResponse | None:
    payload = _verify_share_token(token)
    run_id = payload.get("run_id") if payload else None
    if not run_id:
        return None

    run = _pipelines.get(run_id)
    if not run:
        return None

    project_id = _pipeline_project_map.get(run_id)
    spec_id = _pipeline_spec_map.get(run_id)
    project_name = _projects.get(project_id).name if project_id and _projects.get(project_id) else None
    spec_title = _specs.get(spec_id).title if spec_id and _specs.get(spec_id) else None

    return SharedRunResponse(
        run_id=run.id,
        status=run.status,
        created_at=_pipeline_created_at.get(run.id) or datetime.utcnow(),
        project_name=project_name,
        spec_title=spec_title,
        result=run.result,
    )


def get_profile(user_id: str, email: str | None = None) -> ProfileResponse:
    existing = _profiles.get(user_id)
    if existing:
        if email and existing.email != email:
            existing.email = email
        return existing

    profile = ProfileResponse(id=user_id, email=email)
    _profiles[user_id] = profile
    return profile


def update_profile(user_id: str, payload: ProfileUpdate, email: str | None = None) -> ProfileResponse:
    profile = get_profile(user_id=user_id, email=email)
    data = payload.model_dump(exclude_none=True)
    for key, value in data.items():
        setattr(profile, key, value)
    return profile
