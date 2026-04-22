from fastapi import APIRouter, Depends, HTTPException
from datetime import datetime

from app.core.config import settings
from app.core.security import get_current_user
from app.schemas import PlanSummary, ProfileResponse, ProfileUpdate
from app.storage.repo import get_profile, get_plan_summary, update_profile

router = APIRouter(prefix="/profile", tags=["profile"])


@router.get("/me", response_model=ProfileResponse)
def get_my_profile(user=Depends(get_current_user)):
    if not settings.auth_enabled:
        return ProfileResponse(id="dev-profile", email="dev@baxel.local", username="dev", full_name="Dev User")
    return get_profile(user_id=user.get("sub"), email=user.get("email"))


@router.patch("/me", response_model=ProfileResponse)
def update_my_profile(payload: ProfileUpdate, user=Depends(get_current_user)):
    if not settings.auth_enabled:
        return ProfileResponse(
            id="dev-profile",
            email="dev@baxel.local",
            username=payload.username or "dev",
            full_name=payload.full_name or "Dev User",
            avatar_url=payload.avatar_url,
        )
    try:
        return update_profile(user_id=user.get("sub"), payload=payload, email=user.get("email"))
    except Exception as error:
        message = str(error)
        if "duplicate key value" in message and "profiles_username_key" in message:
            raise HTTPException(status_code=409, detail="Username is already taken")
        raise


@router.get("/plan", response_model=PlanSummary)
def get_my_plan(user=Depends(get_current_user)):
    if not settings.auth_enabled:
        today = datetime.utcnow().date().isoformat()
        return PlanSummary(
            plan_name="Starter",
            plan_code="starter",
            status="active",
            monthly_run_limit=9,
            runs_used_this_month=0,
            monthly_project_limit=3,
            projects_used_this_month=0,
            runs_per_project_limit=3,
            idea_char_limit=1000,
            billing_period=f"{today} to {today}",
            manage_url=None,
        )
    return get_plan_summary(user_id=user.get("sub"))
