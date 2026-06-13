import os
import logging
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv

from app.core.db import get_db
from app.models.spec_db import SpecModel

from pathlib import Path

load_dotenv()
logger = logging.getLogger(__name__)

router = APIRouter()

def _read_env_file_value(key: str) -> str:
    """
    Reads the value of a key from the .env file directly.
    Searches current directory and parent directories (since app is running from app/ or backend/).
    """
    paths_to_check = [
        Path(".env"),
        Path(__file__).resolve().parents[2] / ".env",  # backend/.env
        Path(__file__).resolve().parents[3] / ".env"
    ]
    for env_file in paths_to_check:
        if env_file.exists():
            try:
                lines = env_file.read_text(encoding="utf-8-sig", errors="ignore").splitlines()
                for raw_line in lines:
                    line = raw_line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    left, right = line.split("=", 1)
                    if left.strip() == key:
                        return right.strip().strip('"').strip("'")
            except Exception:
                pass
    return ""

def _load_api_key() -> str:
    return os.getenv("NVIDIA_API_KEY", "").strip() or _read_env_file_value("NVIDIA_API_KEY")

class ChatRequest(BaseModel):
    message: str = Field(..., description="The user message to send to the chatbot")
    spec_id: uuid.UUID = Field(..., description="The ID of the generated architecture spec context")

def get_llm_client():
    api_key = _load_api_key()
    if not api_key:
        return None
    base_url = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
    return OpenAI(api_key=api_key, base_url=base_url)

def classify_query_intent(client: Any, message: str) -> str:
    """
    Runs the user message through a lightweight LLM classifier
    to detect if it requires full technical architecture spec context.
    """
    if not client:
        # Fallback local regex classifier
        prompt_lower = message.lower()
        tech_keywords = {
            "scale", "performance", "table", "column", "foreign", "key", "index", 
            "endpoint", "route", "api", "schema", "database", "query", "code", "docker", 
            "connect", "relation", "type", "model", "package", "lock", "websocket"
        }
        if any(kw in prompt_lower for kw in tech_keywords):
            return "technical"
        return "business"

    try:
        classifier_prompt = f"""
        Classify the following user message into either 'technical' or 'business'.
        
        - 'technical': If the question asks for specific code implementation, table schemas, relationships, database columns, API routes, pagination, or technical scaling limits (e.g., 'Will this scale to 1 million users?').
        - 'business': If the question asks for pitch summaries, AWS running costs, business metrics, or high-level non-technical descriptions.
        
        User Message: "{message}"
        
        Response MUST be exactly one word: 'technical' or 'business'.
        """
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "meta/llama-3.1-70b-instruct"),
            messages=[{"role": "user", "content": classifier_prompt}],
            temperature=0.0,
            max_tokens=5
        )
        intent = response.choices[0].message.content.strip().lower()
        if "technical" in intent:
            return "technical"
        return "business"
    except Exception as e:
        logger.warning(f"Failed to run LLM intent classifier: {e}. Defaulting to keyword check.")
        # Re-run local fallback
        return classify_query_intent(None, message)

@router.post("/chat")
async def chat_with_spec(request: ChatRequest, db: Session = Depends(get_db)):
    spec_id_str = str(request.spec_id)
    
    # Retrieve the architecture spec from the DB
    spec_record = db.query(SpecModel).filter(SpecModel.id == spec_id_str).first()
    if not spec_record:
        raise HTTPException(status_code=404, detail="Architecture spec not found in database.")
        
    spec_json = spec_record.generated_json
    prompt_used = spec_record.prompt_used
    
    client = get_llm_client()
    
    # 1. Classify the user query intent to protect context limits
    intent = classify_query_intent(client, request.message)
    logger.info(f"Chat message intent classified as: {intent}")
    
    # 2. Build system context based on intent
    if intent == "technical":
        # Inject full technical detail
        system_context = f"""
        You are a Principal Software Architect AI Assistant. 
        You are helping the user build or modify the following architecture:
        
        Original User Prompt: {prompt_used}
        
        Full Architecture Specification (JSON):
        {spec_json}
        
        Answering technical queries: Refer directly to specific tables, fields, columns, and REST API paths present in the JSON context.
        """
    else:
        # Inject lightweight summary to optimize costs
        tech_stack = spec_json.get("tech_stack", {})
        auth_strategy = spec_json.get("auth_strategy", {})
        project_name = spec_json.get("project_name", "BaxelProject")
        
        system_context = f"""
        You are a Principal Systems Architect and Business Consultant.
        You are helping a founder/developer build the project '{project_name}'.
        
        Original User Prompt: {prompt_used}
        Tech Stack: {tech_stack.get('language')} / {tech_stack.get('framework')} with {tech_stack.get('database_engine')}
        Auth Method: {auth_strategy.get('method')}
        
        Answering business/high-level queries: Do not reference deep table column details unless asked, focus on high-level costs, summaries, and value.
        """
        
    # 3. Call LLM to chat
    if not client:
        # Offline Mock Chat Response
        mock_replies = {
            "technical": f"Mock Technical Response: Based on your architecture, we are using {spec_json.get('tech_stack', {}).get('database_engine')}. Your tables include {', '.join([t.get('name') for t in spec_json.get('database', {}).get('tables', [])])}.",
            "business": f"Mock Business Response: The {spec_json.get('project_name')} project runs on a highly cost-efficient stack. Using standard AWS serverless or Fargate containers, hosting will scale gracefully starting at ~$20/month."
        }
        return {"reply": mock_replies.get(intent)}
        
    try:
        response = client.chat.completions.create(
            model=os.getenv("LLM_MODEL", "meta/llama-3.1-70b-instruct"),
            messages=[
                {"role": "system", "content": system_context},
                {"role": "user", "content": request.message}
            ]
        )
        reply = response.choices[0].message.content
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Failed to generate LLM chat reply: {e}")
        raise HTTPException(status_code=500, detail=f"LLM Chat Error: {str(e)}")
