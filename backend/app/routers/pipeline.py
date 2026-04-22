from fastapi import APIRouter, Depends, HTTPException
from fastapi import Response
import logging
from app.core.config import settings
from app.core.plan_guard import assert_plan_allows_access
from app.core.security import get_current_user
from app.schemas import PipelineRunListItem, PipelineRunRequest, PipelineRunResponse, PipelineStatus
from app.services.pipeline_service import run_pipeline, new_pipeline_status
from app.storage.repo import get_spec, create_pipeline, update_pipeline, get_pipeline, list_pipeline_runs, store_pipeline_outputs, get_plan_summary, enforce_project_pipeline_limit

router = APIRouter(prefix="/pipelines", tags=["pipelines"])
logger = logging.getLogger(__name__)


def _allowed_output_keys(plan_code: str) -> set[str]:
    normalized = str(plan_code or "starter").strip().lower()
    if normalized == "starter":
        return {"summary", "entities", "relationships", "join_tables", "endpoints"}
    if normalized == "creator":
        return {"summary", "entities", "relationships", "join_tables", "endpoints", "migration_sql", "rules"}
    return {"summary", "entities", "relationships", "join_tables", "endpoints", "migration_sql", "rules", "code_skeleton"}


def _filter_result_for_plan(result: dict | None, plan_code: str) -> dict | None:
    if not isinstance(result, dict):
        return result
    allowed = _allowed_output_keys(plan_code)
    filtered = {key: value for key, value in result.items() if key in allowed or key.startswith("__")}
    filtered.setdefault("summary", result.get("summary"))
    return filtered


@router.get("", response_model=list[PipelineRunListItem])
def list_pipeline_history(user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    return list_pipeline_runs(user_id=user_id, limit=100)


@router.get("/history", response_model=list[PipelineRunListItem])
def list_pipeline_history_alias(user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    return list_pipeline_runs(user_id=user_id, limit=100)


@router.post("/run", response_model=PipelineRunResponse)
def run_pipeline_job(payload: PipelineRunRequest, response: Response, user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    try:
        enforce_project_pipeline_limit(project_id=payload.project_id, user_id=user_id)
    except RuntimeError as error:
        message = str(error)
        if "per-project pipeline limit reached" in message.lower() or "upgrade required" in message.lower():
            raise HTTPException(status_code=402, detail=message)
        raise HTTPException(status_code=500, detail=message)
    plan = get_plan_summary(user_id=user_id)
    logger.info(
        "pipeline.run.start user_id=%s project_id=%s spec_id=%s",
        user_id,
        payload.project_id,
        payload.spec_id,
    )
    spec = get_spec(payload.spec_id, user_id=user_id)
    if not spec:
        raise HTTPException(status_code=404, detail="Spec not found")

    status = new_pipeline_status()
    raw_result = run_pipeline(spec.content, plan_code=plan.plan_code)
    status.result = _filter_result_for_plan(raw_result, plan.plan_code)
    stored = create_pipeline(
        status,
        project_id=payload.project_id,
        spec_id=payload.spec_id,
        user_id=user_id,
    )
    if status.result:
        store_pipeline_outputs(stored.id, status.result)

    result_meta = status.result.get("__meta", {}) if isinstance(status.result, dict) else {}
    generation_source = str(result_meta.get("source") or "unknown")
    generation_model = str(result_meta.get("model") or "unknown")
    response.headers["x-baxel-generation-source"] = generation_source
    response.headers["x-baxel-generation-model"] = generation_model
    response.headers["x-baxel-plan-code"] = plan.plan_code
    logger.info(
        "pipeline.run.end pipeline_id=%s source=%s model=%s entities=%s endpoints=%s rules=%s",
        stored.id,
        generation_source,
        generation_model,
        len((status.result or {}).get("entities") or []),
        len((status.result or {}).get("endpoints") or []),
        len((status.result or {}).get("rules") or []),
    )

    return PipelineRunResponse(id=stored.id, status=stored.status, result=status.result)


@router.get("/{pipeline_id}", response_model=PipelineStatus)
def get_pipeline_status(pipeline_id: str, user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    pipeline = get_pipeline(pipeline_id, user_id=user_id)
    if not pipeline:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    return pipeline
