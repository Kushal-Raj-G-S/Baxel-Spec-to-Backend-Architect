from typing import Dict, Any, List
import uuid
import logging

from app.schemas import PipelineStatus
from app.services.spec_parser import build_blueprint

logger = logging.getLogger(__name__)


def run_pipeline(spec_text: str) -> Dict[str, Any]:
    result = build_blueprint(spec_text)
    meta = result.get("__meta", {}) if isinstance(result, dict) else {}
    logger.info(
        "pipeline.run.generated source=%s provider=%s model=%s entities=%s endpoints=%s rules=%s",
        meta.get("source", "unknown"),
        meta.get("provider", "unknown"),
        meta.get("model", "unknown"),
        len(result.get("entities") or []),
        len(result.get("endpoints") or []),
        len(result.get("rules") or []),
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
