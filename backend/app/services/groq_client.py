from typing import Dict, Any
import httpx
from app.core.config import settings

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


def call_groq(system_prompt: str, user_prompt: str) -> Dict[str, Any]:
    if not settings.groq_api_key:
        return {"error": "GROQ_API_KEY not set"}

    payload = {
        "model": "llama3-70b-8192",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        "temperature": 0.2
    }

    headers = {"Authorization": f"Bearer {settings.groq_api_key}"}

    with httpx.Client(timeout=30) as client:
        response = client.post(GROQ_ENDPOINT, json=payload, headers=headers)
        response.raise_for_status()
        return response.json()
