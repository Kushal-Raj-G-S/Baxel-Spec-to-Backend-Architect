from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.core.security import get_current_user
from app.schemas import SharedRunResponse, ShareTokenResponse
from app.storage.repo import create_share_token, get_shared_run_by_token

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("/{run_id}/share", response_model=ShareTokenResponse)
def get_share_token_for_run(run_id: str, user=Depends(get_current_user)):
    user_id = user.get("sub") if settings.auth_enabled else None
    shared = create_share_token(run_id=run_id, user_id=user_id)
    if not shared:
        raise HTTPException(status_code=404, detail="Run not found")
    return shared


@router.get("/share/{token}", response_model=SharedRunResponse)
def get_shared_run(token: str):
    shared_run = get_shared_run_by_token(token)
    if not shared_run:
        raise HTTPException(status_code=404, detail="Invalid or expired share token")
    return shared_run
