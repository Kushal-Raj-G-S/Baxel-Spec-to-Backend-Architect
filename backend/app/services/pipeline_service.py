from typing import Dict, Any, List
import uuid
import logging

from app.schemas import PipelineStatus
from app.services.spec_parser import build_blueprint, expand_spec_for_pipeline

logger = logging.getLogger(__name__)


def run_pipeline(spec_text: str, plan_code: str | None = None) -> Dict[str, Any]:
    expansion = expand_spec_for_pipeline(spec_text, plan_code=plan_code)
    expanded_spec = str(expansion.get("expanded_spec") or spec_text or "")
    result = build_blueprint(expanded_spec, plan_code=plan_code)
    if isinstance(result, dict):
        meta = result.setdefault("__meta", {})
        if isinstance(meta, dict):
            meta["spec_expansion"] = {
                "source": expansion.get("source"),
                "model": expansion.get("model"),
                "original_chars": expansion.get("original_chars", len(spec_text or "")),
                "expanded_chars": expansion.get("expanded_chars", len(expanded_spec)),
                "inferred_count": expansion.get("inferred_count", 0),
            }
            meta["content_chars"] = len(expanded_spec)
    meta = result.get("__meta", {}) if isinstance(result, dict) else {}
    logger.info(
        "pipeline.run.generated source=%s provider=%s model=%s entities=%s endpoints=%s rules=%s expand_source=%s expand_chars=%s",
        meta.get("source", "unknown"),
        meta.get("provider", "unknown"),
        meta.get("model", "unknown"),
        len(result.get("entities") or []),
        len(result.get("endpoints") or []),
        len(result.get("rules") or []),
        ((meta.get("spec_expansion") or {}).get("source") if isinstance(meta, dict) else "unknown"),
        ((meta.get("spec_expansion") or {}).get("expanded_chars") if isinstance(meta, dict) else "unknown"),
    )
    return result


def new_pipeline_status() -> PipelineStatus:
    stages: List[Dict[str, str]] = [
        {"name": "Spec cleanup", "status": "done"},
        {"name": "Entities & relations", "status": "done"},
        {"name": "Model proposal", "status": "done"},
        {"name": "API surface", "status": "done"},
        {"name": "Business rules", "status": "done"},
        {"name": "Code skeleton", "status": "done"}
    ]

    return PipelineStatus(id=str(uuid.uuid4()), status="completed", stages=stages, result=None)
