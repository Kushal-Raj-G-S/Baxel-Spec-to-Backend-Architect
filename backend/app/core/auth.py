import os
import json
import logging
from typing import Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from fastapi import Header, HTTPException, status

logger = logging.getLogger(__name__)

def _validate_token_with_supabase(token: str) -> Dict:
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_anon_key = os.getenv("SUPABASE_ANON_KEY")
    
    if not supabase_url or not supabase_anon_key:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="SUPABASE_URL or SUPABASE_ANON_KEY environment variables are missing",
        )

    # Call Supabase Auth API to get user info
    request = Request(
        url=f"{supabase_url}/auth/v1/user",
        headers={
            "Authorization": f"Bearer {token}",
            "apikey": supabase_anon_key,
        },
        method="GET",
    )

    try:
        with urlopen(request, timeout=8) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except HTTPError as error:
        if error.code == 401:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Auth provider error: {error.code}")
    except URLError as error:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail=f"Unable to reach auth provider: {error.reason}")

    if not payload.get("id"):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")

    return {
        "sub": payload.get("id"),
        "email": payload.get("email"),
        "user_metadata": payload.get("user_metadata") or {},
    }

def get_current_user(authorization: str | None = Header(default=None)) -> Dict:
    auth_enabled = os.getenv("AUTH_ENABLED", "true").lower() == "true"
    if not auth_enabled:
        return {
            "sub": "00000000-0000-0000-0000-000000000001",
            "email": "dev@baxel.local",
            "user_metadata": {"workspace_name": "Baxel Dev Local"}
        }

    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing bearer token")

    token = authorization.split(" ", 1)[1]
    return _validate_token_with_supabase(token)
