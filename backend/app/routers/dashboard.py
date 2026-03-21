from fastapi import APIRouter, Depends

from app.core.config import settings
from app.core.security import get_current_user
from app.schemas import DashboardSummary, PublicMetrics
from app.storage.repo import get_dashboard_summary, get_public_metrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/summary", response_model=DashboardSummary)
def dashboard_summary(user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    return get_dashboard_summary(user_id=user_id)


@router.get("/public-metrics", response_model=PublicMetrics)
def dashboard_public_metrics():
    return get_public_metrics()
