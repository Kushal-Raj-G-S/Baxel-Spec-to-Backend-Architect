import json
from typing import Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import Header, HTTPException, status
from app.core.config import settings


def _validate_token_with_supabase(token: str) -> Dict:
    if not settings.supabase_url or not settings.supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_URL or SUPABASE_ANON_KEY is missing",
        )

    request = Request(
        url=f"{settings.supabase_url}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": settings.supabase_anon_key,
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Auth provider error")
    except URLError:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Unable to reach auth provider")

    if not payload.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return {
        "sub": payload.get("id"),
        "email": payload.get("email"),
        "user_metadata": payload.get("user_metadata") or {},
    }


def get_current_user(authorization: str | None = Header(default=None)) -> Dict:
    if not settings.auth_enabled:
        return {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "dev@baxel.local",
        }

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]

    return _validate_token_with_supabase(token)
