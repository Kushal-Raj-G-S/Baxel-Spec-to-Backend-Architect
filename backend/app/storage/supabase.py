from datetime import datetime, timezone
from typing import Any, Dict, List
import base64
import hashlib
import hmac
import json

from supabase import Client, create_client

from app.core.config import settings
from app.schemas import (
        ProfileResponse,
        ProfileUpdate,
    DashboardPipelineItem,
    DashboardProjectItem,
    DashboardSummary,
    PlanSummary,
    ProjectHistory,
    ProjectHistoryRunItem,
    PublicMetrics,
    PipelineRunListItem,
    SharedRunResponse,
    ShareTokenResponse,
    PipelineStatus,
    Project,
    ProjectCreate,
    Spec,
    SpecCreate,
)

_client: Client | None = None


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    return None


def _share_secret() -> str:
    return settings.supabase_jwt_secret or settings.supabase_service_role_key or "baxel-share-secret"


def _sign_share_payload(payload: dict) -> str:
    raw = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    encoded = base64.urlsafe_b64encode(raw).decode("utf-8").rstrip("=")
    signature = hmac.new(_share_secret().encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{encoded}.{signature}"


def _verify_share_token(token: str) -> dict | None:
    if "." not in token:
        return None
    encoded, signature = token.rsplit(".", 1)
    expected = hmac.new(_share_secret().encode("utf-8"), encoded.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None

    padding = "=" * ((4 - len(encoded) % 4) % 4)
    try:
        payload = json.loads(base64.urlsafe_b64decode((encoded + padding).encode("utf-8")).decode("utf-8"))
    except Exception:
        return None
    return payload if isinstance(payload, dict) else None


def _get_client() -> Client:
    global _client
    if _client is None:
        if not settings.supabase_url or not settings.supabase_service_role_key:
            raise RuntimeError("Supabase is not configured")
        _client = create_client(settings.supabase_url, settings.supabase_service_role_key)
    return _client


def _first(data):
    if isinstance(data, list):
        return data[0] if data else None
    return data


def create_project(payload: ProjectCreate, user_id: str | None = None) -> Project:
    client = _get_client()
    normalized_name = (payload.name or "").strip()
    if not normalized_name:
        raise RuntimeError("Project name is required")

    query = client.table("projects").select("*").ilike("name", normalized_name)
    if user_id:
        query = query.eq("user_id", user_id)
    else:
        query = query.is_("user_id", "null")

    existing_res = query.order("created_at", desc=True).limit(1).execute()
    existing = _first(existing_res.data)

    if existing:
        update_payload: Dict[str, Any] = {}
        if payload.description and payload.description != existing.get("description"):
            update_payload["description"] = payload.description
            update_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        if update_payload:
            updated_res = client.table("projects").update(update_payload).eq("id", existing.get("id")).execute()
            existing = _first(updated_res.data) or existing
        return Project.model_validate(existing)

    data = payload.model_dump()
    data["name"] = normalized_name
    data["user_id"] = user_id
    response = client.table("projects").insert(data).execute()
    record = _first(response.data)
    if not record:
        raise RuntimeError("Failed to create project")
    return Project.model_validate(record)


def list_projects(user_id: str | None = None) -> List[Project]:
    client = _get_client()
    query = client.table("projects").select("*")
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.execute()
    return [Project.model_validate(item) for item in (response.data or [])]


def get_project(project_id: str, user_id: str | None = None) -> Project | None:
    client = _get_client()
    query = client.table("projects").select("*").eq("id", project_id)
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.execute()
    record = _first(response.data)
    if not record:
        return None
    return Project.model_validate(record)


def get_project_history(project_id: str, user_id: str | None = None) -> ProjectHistory | None:
    client = _get_client()
    project = get_project(project_id, user_id=user_id)
    if not project:
        return None

    specs_q = client.table("specs").select("id,title,created_at").eq("project_id", project_id)
    specs_count_q = client.table("specs").select("id", count="exact").eq("project_id", project_id)
    runs_q = (
        client.table("pipeline_runs")
        .select("id,status,created_at,spec_id,result")
        .eq("project_id", project_id)
        .order("created_at", desc=True)
        .limit(10)
    )
    runs_count_q = client.table("pipeline_runs").select("id", count="exact").eq("project_id", project_id)

    if user_id:
        specs_q = specs_q.eq("user_id", user_id)
        specs_count_q = specs_count_q.eq("user_id", user_id)
        runs_q = runs_q.eq("user_id", user_id)
        runs_count_q = runs_count_q.eq("user_id", user_id)

    specs_res = specs_q.execute()
    specs_count_res = specs_count_q.execute()
    runs_res = runs_q.execute()
    runs_count_res = runs_count_q.execute()

    spec_lookup = {
        item.get("id"): item.get("title")
        for item in (specs_res.data or [])
        if item.get("id")
    }

    return ProjectHistory(
        project=project,
        specs_count=specs_count_res.count or 0,
        pipeline_runs_count=runs_count_res.count or 0,
        recent_runs=[
            ProjectHistoryRunItem(
                id=item.get("id"),
                status=item.get("status"),
                created_at=item.get("created_at"),
                spec_id=item.get("spec_id"),
                spec_title=spec_lookup.get(item.get("spec_id")),
                result=item.get("result"),
            )
            for item in (runs_res.data or [])
            if item.get("id") and item.get("status") and item.get("created_at")
        ],
    )


def list_projects_history(user_id: str | None = None, limit: int = 100) -> List[ProjectHistory]:
    projects = list_projects(user_id=user_id)
    histories: List[ProjectHistory] = []
    for project in projects[:limit]:
        history = get_project_history(project.id, user_id=user_id)
        if history:
            histories.append(history)
    return histories


def create_spec(payload: SpecCreate, user_id: str | None = None) -> Spec:
    client = _get_client()
    data = payload.model_dump()
    data["user_id"] = user_id
    response = client.table("specs").insert(data).execute()
    record = _first(response.data)
    if not record:
        raise RuntimeError("Failed to create spec")
    return Spec.model_validate(record)


def list_specs(project_id: str, user_id: str | None = None) -> List[Spec]:
    client = _get_client()
    query = client.table("specs").select("*").eq("project_id", project_id)
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.execute()
    return [Spec.model_validate(item) for item in (response.data or [])]


def get_spec(spec_id: str, user_id: str | None = None) -> Spec | None:
    client = _get_client()
    query = client.table("specs").select("*").eq("id", spec_id)
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.execute()
    record = _first(response.data)
    if not record:
        return None
    return Spec.model_validate(record)


def create_pipeline(
    status: PipelineStatus,
    project_id: str | None = None,
    spec_id: str | None = None,
    user_id: str | None = None,
) -> PipelineStatus:
    client = _get_client()
    payload = status.model_dump()
    payload["project_id"] = project_id
    payload["spec_id"] = spec_id
    payload["user_id"] = user_id
    if status.status.lower() == "completed":
        payload["completed_at"] = datetime.now(timezone.utc).isoformat()
    response = client.table("pipeline_runs").insert(payload).execute()
    record = _first(response.data)
    if not record:
        raise RuntimeError("Failed to create pipeline run")
    return PipelineStatus.model_validate(record)


def update_pipeline(status: PipelineStatus) -> PipelineStatus:
    client = _get_client()
    payload = status.model_dump()
    response = client.table("pipeline_runs").update(payload).eq("id", status.id).execute()
    record = _first(response.data)
    if not record:
        raise RuntimeError("Failed to update pipeline run")
    return PipelineStatus.model_validate(record)


def get_pipeline(pipeline_id: str, user_id: str | None = None) -> PipelineStatus | None:
    client = _get_client()
    query = client.table("pipeline_runs").select("*").eq("id", pipeline_id)
    if user_id:
        query = query.eq("user_id", user_id)
    response = query.execute()
    record = _first(response.data)
    if not record:
        return None
    return PipelineStatus.model_validate(record)


def list_pipeline_runs(user_id: str | None = None, limit: int = 50) -> List[PipelineRunListItem]:
    client = _get_client()
    query = (
        client.table("pipeline_runs")
        .select("id,status,created_at,completed_at,spec_id,project_id")
        .order("created_at", desc=True)
        .limit(limit)
    )
    if user_id:
        query = query.eq("user_id", user_id)

    runs_res = query.execute()
    runs = runs_res.data or []
    spec_ids = [item.get("spec_id") for item in runs if item.get("spec_id")]
    project_ids = [item.get("project_id") for item in runs if item.get("project_id")]

    spec_lookup: Dict[str, str] = {}
    project_lookup: Dict[str, str] = {}

    if spec_ids:
        specs_res = client.table("specs").select("id,title").in_("id", spec_ids).execute()
        spec_lookup = {item.get("id"): item.get("title") for item in (specs_res.data or []) if item.get("id")}

    if project_ids:
        projects_res = client.table("projects").select("id,name").in_("id", project_ids).execute()
        project_lookup = {item.get("id"): item.get("name") for item in (projects_res.data or []) if item.get("id")}

    items: List[PipelineRunListItem] = []
    for item in runs:
        created_at = _parse_datetime(item.get("created_at"))
        if not created_at:
            continue

        completed_at = None
        duration_seconds = None
        completed_at = _parse_datetime(item.get("completed_at"))
        if completed_at:
            duration_seconds = max(0, int((completed_at - created_at).total_seconds()))

        items.append(
            PipelineRunListItem(
                id=item.get("id"),
                status=item.get("status"),
                created_at=created_at,
                completed_at=completed_at,
                project_name=project_lookup.get(item.get("project_id")),
                spec_title=spec_lookup.get(item.get("spec_id")),
                duration_seconds=duration_seconds,
            )
        )

    return items


def store_pipeline_outputs(pipeline_id: str, outputs: Dict[str, Any]) -> None:
    client = _get_client()

    entities = outputs.get("entities") or []
    if entities:
        payload = [
            {"pipeline_run_id": pipeline_id, "name": item.get("name"), "fields": item.get("fields")}
            for item in entities
        ]
        client.table("entities").insert(payload).execute()

    endpoints = outputs.get("endpoints") or []
    if endpoints:
        payload = [
            {
                "pipeline_run_id": pipeline_id,
                "method": item.get("method"),
                "path": item.get("path"),
                "description": item.get("desc")
            }
            for item in endpoints
        ]
        client.table("endpoints").insert(payload).execute()

    rules = outputs.get("rules") or []
    if rules:
        payload = [{"pipeline_run_id": pipeline_id, "rule_text": rule} for rule in rules]
        client.table("business_rules").insert(payload).execute()


def get_dashboard_summary(user_id: str | None = None) -> DashboardSummary:
    client = _get_client()

    projects_q = client.table("projects").select("id", count="exact")
    specs_q = client.table("specs").select("id", count="exact")
    runs_q = client.table("pipeline_runs").select("id", count="exact")

    if user_id:
        projects_q = projects_q.eq("user_id", user_id)
        specs_q = specs_q.eq("user_id", user_id)
        runs_q = runs_q.eq("user_id", user_id)

    projects_res = projects_q.execute()
    specs_res = specs_q.execute()
    runs_res = runs_q.execute()

    recent_projects_q = client.table("projects").select("id,name,created_at").order("created_at", desc=True).limit(5)
    recent_runs_q = (
        client.table("pipeline_runs")
        .select("id,status,created_at,spec_id,project_id")
        .order("created_at", desc=True)
        .limit(5)
    )

    if user_id:
        recent_projects_q = recent_projects_q.eq("user_id", user_id)
        recent_runs_q = recent_runs_q.eq("user_id", user_id)

    recent_projects_res = recent_projects_q.execute()
    recent_runs_res = recent_runs_q.execute()

    recent_runs = recent_runs_res.data or []
    spec_ids = [item.get("spec_id") for item in recent_runs if item.get("spec_id")]
    project_ids = [item.get("project_id") for item in recent_runs if item.get("project_id")]

    spec_lookup: Dict[str, str] = {}
    project_lookup: Dict[str, str] = {}

    if spec_ids:
        spec_titles_res = client.table("specs").select("id,title").in_("id", spec_ids).execute()
        spec_lookup = {item.get("id"): item.get("title") for item in (spec_titles_res.data or []) if item.get("id")}

    if project_ids:
        project_titles_res = client.table("projects").select("id,name").in_("id", project_ids).execute()
        project_lookup = {item.get("id"): item.get("name") for item in (project_titles_res.data or []) if item.get("id")}

    return DashboardSummary(
        projects_count=projects_res.count or 0,
        specs_count=specs_res.count or 0,
        pipeline_runs_count=runs_res.count or 0,
        recent_projects=[DashboardProjectItem.model_validate(item) for item in (recent_projects_res.data or [])],
        recent_pipeline_runs=[
            DashboardPipelineItem(
                id=item.get("id"),
                status=item.get("status"),
                created_at=item.get("created_at"),
                spec_title=spec_lookup.get(item.get("spec_id")),
                project_name=project_lookup.get(item.get("project_id")),
            )
            for item in recent_runs
            if item.get("created_at")
        ],
    )


def get_public_metrics() -> PublicMetrics:
    client = _get_client()

    specs_res = client.table("specs").select("id", count="exact").execute()
    runs_res = client.table("pipeline_runs").select("id", count="exact").execute()
    endpoints_res = client.table("endpoints").select("id", count="exact").execute()
    rules_res = client.table("business_rules").select("id", count="exact").execute()

    return PublicMetrics(
        specs_processed=specs_res.count or 0,
        schemas_generated=runs_res.count or 0,
        api_endpoints=endpoints_res.count or 0,
        rules_captured=rules_res.count or 0,
    )


def get_plan_summary(user_id: str | None = None) -> PlanSummary:
    client = _get_client()

    now = datetime.now(timezone.utc)
    month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    runs_q = client.table("pipeline_runs").select("id", count="exact").gte("created_at", month_start.isoformat())
    if user_id:
        runs_q = runs_q.eq("user_id", user_id)
    runs_res = runs_q.execute()
    runs_used_this_month = runs_res.count or 0

    default_summary = PlanSummary(
        plan_name="Starter",
        status="active",
        monthly_run_limit=3,
        runs_used_this_month=runs_used_this_month,
        billing_period=f"{month_start.date().isoformat()} to {now.date().isoformat()}",
        period_start=month_start,
        period_end=now,
        manage_url=None,
    )

    if not user_id:
        return default_summary

    try:
        sub_res = (
            client.table("subscriptions")
            .select("plan_name,status,monthly_run_limit,period_start,period_end,manage_url")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(1)
            .execute()
        )
        sub = _first(sub_res.data)
        if not sub:
            return default_summary

        sub_period_start = _parse_datetime(sub.get("period_start")) or month_start
        sub_period_end = _parse_datetime(sub.get("period_end")) or now

        return PlanSummary(
            plan_name=sub.get("plan_name") or "Starter",
            status=sub.get("status") or "active",
            monthly_run_limit=sub.get("monthly_run_limit") or 3,
            runs_used_this_month=runs_used_this_month,
            billing_period=f"{sub_period_start.date().isoformat()} to {sub_period_end.date().isoformat()}",
            period_start=sub_period_start,
            period_end=sub_period_end,
            manage_url=sub.get("manage_url"),
        )
    except Exception:
        return default_summary


def create_share_token(run_id: str, user_id: str | None = None) -> ShareTokenResponse | None:
    pipeline = get_pipeline(run_id, user_id=user_id)
    if not pipeline:
        return None

    payload = {
        "run_id": run_id,
        "issued_at": datetime.now(timezone.utc).isoformat(),
    }
    return ShareTokenResponse(token=_sign_share_payload(payload))


def get_shared_run_by_token(token: str) -> SharedRunResponse | None:
    payload = _verify_share_token(token)
    run_id = payload.get("run_id") if payload else None
    if not run_id:
        return None

    client = _get_client()
    run_res = (
        client.table("pipeline_runs")
        .select("id,status,created_at,project_id,spec_id,result")
        .eq("id", run_id)
        .limit(1)
        .execute()
    )
    run = _first(run_res.data)
    if not run:
        return None

    project_name = None
    spec_title = None
    project_id = run.get("project_id")
    spec_id = run.get("spec_id")

    if project_id:
        project_res = client.table("projects").select("name").eq("id", project_id).limit(1).execute()
        project_name = (_first(project_res.data) or {}).get("name")
    if spec_id:
        spec_res = client.table("specs").select("title").eq("id", spec_id).limit(1).execute()
        spec_title = (_first(spec_res.data) or {}).get("title")

    created_at = _parse_datetime(run.get("created_at"))
    if not created_at:
        return None

    return SharedRunResponse(
        run_id=run.get("id"),
        status=run.get("status"),
        created_at=created_at,
        project_name=project_name,
        spec_title=spec_title,
        result=run.get("result") or {},
    )


def get_profile(user_id: str, email: str | None = None) -> ProfileResponse:
    client = _get_client()
    response = client.table("profiles").select("*").eq("id", user_id).execute()
    record = _first(response.data)

    if not record:
        insert_payload = {"id": user_id, "email": email}
        insert_res = client.table("profiles").insert(insert_payload).execute()
        record = _first(insert_res.data)

    return ProfileResponse.model_validate(record)


def update_profile(user_id: str, payload: ProfileUpdate, email: str | None = None) -> ProfileResponse:
    client = _get_client()
    update_payload = payload.model_dump(exclude_none=True)
    if email:
        update_payload["email"] = email
    update_payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    response = client.table("profiles").update(update_payload).eq("id", user_id).execute()
    record = _first(response.data)
    if not record:
        merged_payload = {"id": user_id, "email": email, **payload.model_dump(exclude_none=True)}
        insert_res = client.table("profiles").insert(merged_payload).execute()
        record = _first(insert_res.data)
    return ProfileResponse.model_validate(record)
