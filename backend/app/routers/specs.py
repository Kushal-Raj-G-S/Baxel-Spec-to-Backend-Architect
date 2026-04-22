from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.core.plan_guard import assert_plan_allows_access
from app.core.security import get_current_user
from app.schemas import Spec, SpecCreate
from app.storage.repo import create_spec, list_specs, get_project

router = APIRouter(prefix="/specs", tags=["specs"])


@router.get("/{project_id}", response_model=list[Spec])
def list_project_specs(project_id: str, user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    project = get_project(project_id, user_id=user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return list_specs(project_id, user_id=user_id)


@router.post("", response_model=Spec)
def create_new_spec(payload: SpecCreate, user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    project = get_project(payload.project_id, user_id=user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return create_spec(payload, user_id=user_id)
