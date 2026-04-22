from fastapi import APIRouter, Depends, HTTPException
from app.core.config import settings
from app.core.plan_guard import assert_plan_allows_access
from app.core.security import get_current_user
from app.schemas import Project, ProjectCreate, ProjectHistory
from app.storage.repo import create_project, list_projects, get_project, get_project_history, list_projects_history

router = APIRouter(prefix="/projects", tags=["projects"])


@router.get("", response_model=list[Project])
def list_all_projects(user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    return list_projects(user_id=user_id)


@router.post("", response_model=Project)
def create_new_project(payload: ProjectCreate, user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    try:
        return create_project(payload, user_id=user_id)
    except RuntimeError as error:
        message = str(error)
        if "project limit reached" in message.lower() or "upgrade required" in message.lower():
            raise HTTPException(status_code=402, detail=message)
        raise HTTPException(status_code=500, detail=message)


@router.get("/history", response_model=list[ProjectHistory])
def list_all_projects_history(user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    return list_projects_history(user_id=user_id, limit=100)


@router.get("/{project_id}", response_model=Project)
def get_project_by_id(project_id: str, user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    project = get_project(project_id, user_id=user_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.get("/{project_id}/history", response_model=ProjectHistory)
def get_project_history_by_id(project_id: str, user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    assert_plan_allows_access(user_id)
    history = get_project_history(project_id, user_id=user_id)
    if not history:
        raise HTTPException(status_code=404, detail="Project not found")
    return history
