import os
import logging
import uuid
import datetime
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv

from app.core.db import get_db
from app.models.spec_db import SpecModel, PipelineRunModel, ChatMessageModel
from app.core.auth import get_current_user
from app.services.agents.generation import LLM_REVIEW_MODEL, LLM_MODEL, LLM_SAGE_MODEL
from app.api.endpoints.dashboard_api import get_user_plan

from pathlib import Path

load_dotenv(override=True)
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

def save_chat_message_in_background(
    spec_id: str,
    user_id: str,
    query: str,
    response: str,
    intent: str
):
    from app.core.db import SessionLocal
    db = SessionLocal()
    try:
        chat_msg = ChatMessageModel(
            spec_id=spec_id,
            user_id=user_id,
            query=query,
            response=response,
            intent=intent
        )
        db.add(chat_msg)
        db.commit()
        logger.info(f"Successfully saved chat message in background for spec {spec_id}")
    except Exception as e:
        logger.error(f"Failed to save chat message in background: {e}")
    finally:
        db.close()

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
        classifier_system = """You are an intent classifier for a spec-aware chatbot. Classify the user's message into exactly one of two categories:

- 'technical': the question asks for code implementation, table schemas, relationships, database columns, API routes, pagination, or technical scaling limits (e.g. "Will this scale to 1 million users?").
- 'business': the question asks for pitch summaries, hosting/running costs, business metrics, or high-level non-technical descriptions.

Respond with exactly one word — 'technical' or 'business' — and nothing else. No punctuation, no explanation."""
        response = client.chat.completions.create(
            model=os.getenv("LLM_REVIEW_MODEL", LLM_REVIEW_MODEL),
            messages=[
                {"role": "system", "content": classifier_system},
                {"role": "user", "content": message}
            ],
            temperature=0.0,
            max_tokens=700  # LLM_REVIEW_MODEL reasons before answering — 5 tokens (enough for the old non-reasoning 8B model) truncates before it ever writes 'technical'/'business'
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("Classifier returned no content (likely truncated mid-reasoning)")
        intent = content.strip().lower()
        if "technical" in intent:
            return "technical"
        return "business"
    except Exception as e:
        logger.warning(f"Failed to run LLM intent classifier: {e}. Defaulting to keyword check.")
        # Re-run local fallback
        return classify_query_intent(None, message)

@router.post("/chat")
async def chat_with_spec(
    request: ChatRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    uid = user.get("sub")
    spec_id_str = str(request.spec_id)

    plan = get_user_plan(db, uid)
    day_start = datetime.datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    messages_used_today = db.query(ChatMessageModel).filter(
        ChatMessageModel.user_id == uid,
        ChatMessageModel.created_at >= day_start
    ).count()
    if messages_used_today >= plan["chat_daily_limit"]:
        raise HTTPException(
            status_code=403,
            detail=f"Daily SAGE message limit reached ({messages_used_today}/{plan['chat_daily_limit']}) for the {plan['plan_name']}. Upgrade or try again tomorrow."
        )

    # Retrieve the architecture spec from the DB
    spec_record = db.query(SpecModel).filter(SpecModel.id == spec_id_str).first()
    if not spec_record:
        raise HTTPException(status_code=404, detail="Architecture spec not found in database.")
        
    # Retrieve the latest completed pipeline run for this spec to get the generated result
    run_record = db.query(PipelineRunModel).filter(
        PipelineRunModel.spec_id == spec_id_str,
        PipelineRunModel.status == "completed"
    ).order_by(PipelineRunModel.created_at.desc()).first()
    
    if not run_record or not run_record.result:
        raise HTTPException(status_code=404, detail="Generated architecture result not found for this spec.")
        
    spec_json = run_record.result
    logger.info(f"spec_json keys: {list(spec_json.keys())}")
    prompt_used = spec_record.content

    # Map keys correctly to match the actual dashboard SpecModel dictionary structure
    compact_spec = {
        "tech_stack": spec_json.get("tech_stack"),
        "auth_strategy": spec_json.get("auth_strategy"),
        "database_tables": spec_json.get("entities"),
        "database_relationships": spec_json.get("relationships"),
        "endpoints": spec_json.get("endpoints"),
        "business_rules": spec_json.get("rules"),
    }

    msg_lower = request.message.lower()
    if any(kw in msg_lower for kw in ["docker", "compose", "devops", "env", "variables", "setup"]):
        compact_spec["devops"] = spec_json.get("code_skeleton")
    if any(kw in msg_lower for kw in ["chaos", "resilience", "hardening", "failure", "vulnerabilit"]):
        compact_spec["anti_fragility"] = spec_json.get("anti_fragility")
        
    client = get_llm_client()
    
    # 1. Classify the user query intent to protect context limits
    intent = classify_query_intent(client, request.message)
    logger.info(f"Chat message intent classified as: {intent}")
    
    # 2. Build system context based on intent
    if intent == "technical":
        # Inject full technical detail
        system_context = f"""
        You are SAGE (Specification Answering & Guidance Engine), a Principal Software Architect AI Assistant.
        You are helping the user build or modify the following architecture.

        Original User Prompt (the source of truth for what this system is actually supposed to do):
        {prompt_used}

        Full Architecture Specification (JSON) — this is the ONLY source for schema facts:
        {compact_spec}

        GROUNDING RULES — follow strictly:
        1. Every factual claim about tables, columns, relationships, enum values, or endpoints MUST come directly from the JSON above. Never state a relationship, cardinality, or field that isn't explicitly present in it.
        2. If you are not sure whether something is in the JSON, say "I don't see that in the current spec" rather than describing a plausible-sounding version of it.
        3. Do not invent example data, extra tables, or relationships to illustrate a point unless you clearly label them as a suggestion, not something that currently exists.

        CONSISTENCY CHECKING — this is your most important job:
        4. Before answering, check whether the user's question implies a mismatch between the Original User Prompt and the JSON spec (e.g. a role, entity, or rule mentioned in one but not the other, or two parts of the JSON that contradict each other).
        5. If you find a mismatch, say so explicitly and plainly as the FIRST thing in your answer — e.g. "Before I answer: 'provider' and 'support' don't appear anywhere in your original prompt, so this looks like a generation error, not an intentional design choice." Do not proceed to rationalize or justify a value just because it's already in the JSON — its presence in the JSON is not evidence that it's correct.
        6. Never invent a justification for something you can't trace back to the Original User Prompt. If you can't find where a table, field, or role came from, say that plainly instead of guessing a plausible reason for it ("kept for extensibility," "commonly used in this pattern," etc. are not acceptable unless the user's prompt actually supports them).
        7. After flagging any inconsistency, you may still give your best architectural recommendation for how to resolve it — but the flag comes first, not buried at the end.

        - Your name is SAGE. Do NOT mention your name or introduce yourself unless the user explicitly asks who you are.
        """
    else:
        # Inject lightweight summary to optimize costs
        tech_stack = spec_json.get("tech_stack", {})
        auth_strategy = spec_json.get("auth_strategy", {})
        project_name = spec_json.get("entities", [{}])[0].get("name", "Baxel Project") if spec_json.get("entities") else "Baxel Project"
        
        system_context = f"""
        You are SAGE (Specification Answering & Guidance Engine), a Principal Systems Architect and Business Consultant.
        You are helping a founder/developer build the project '{project_name}'.

        Original User Prompt: {prompt_used}
        Tech Stack: {tech_stack.get('language', 'Python')} / {tech_stack.get('framework', 'FastAPI')} with {tech_stack.get('database_engine', 'PostgreSQL')}
        Auth Method: {auth_strategy.get('method', 'JWT')}

        RULES:
        - Focus on high-level costs, summaries, and value — don't dive into table/column detail unless asked.
        - If the user's question touches on something that seems inconsistent with the Original User Prompt (e.g. a feature, role, or cost driver that doesn't match what they actually described), flag that plainly rather than answering as if it were confirmed and correct.
        - Never fabricate a business justification for something you can't trace back to what the user actually asked for.

        - Your name is SAGE. Do NOT mention your name or introduce yourself unless the user explicitly asks who you are.
        """
        
    # 3. Retrieve conversation history (last 5 turns) to provide context memory
    past_messages = db.query(ChatMessageModel).filter(
        ChatMessageModel.spec_id == spec_id_str,
        ChatMessageModel.user_id == uid
    ).order_by(ChatMessageModel.created_at.desc()).limit(5).all()
    
    # Reverse to restore chronological order
    past_messages = past_messages[::-1]
    
    chat_messages = [{"role": "system", "content": system_context}]
    for pm in past_messages:
        chat_messages.append({"role": "user", "content": pm.query})
        chat_messages.append({"role": "assistant", "content": pm.response})
        
    chat_messages.append({"role": "user", "content": request.message})

    # 4. Call LLM to chat
    if not client:
        # Offline Mock Chat Response
        mock_replies = {
            "technical": f"Mock Technical Response: Based on your architecture, we are using {spec_json.get('tech_stack', {}).get('database_engine')}. Your tables include {', '.join([t.get('name') for t in spec_json.get('database', {}).get('tables', [])])}.",
            "business": f"Mock Business Response: The {spec_json.get('project_name')} project runs on a highly cost-efficient stack. Using standard AWS serverless or Fargate containers, hosting will scale gracefully starting at ~$20/month."
        }
        reply = mock_replies.get(intent)
        background_tasks.add_task(
            save_chat_message_in_background,
            spec_id_str,
            uid,
            request.message,
            reply,
            intent
        )
        return {"reply": reply}
        
    try:
        response = client.chat.completions.create(
            model=LLM_SAGE_MODEL,
            messages=chat_messages
        )
        reply = response.choices[0].message.content
        
        # Save query and response to database in background
        background_tasks.add_task(
            save_chat_message_in_background,
            spec_id_str,
            uid,
            request.message,
            reply,
            intent
        )
        
        return {"reply": reply}
    except Exception as e:
        logger.error(f"Failed to generate LLM chat reply: {e}")
        raise HTTPException(status_code=500, detail=f"LLM Chat Error: {str(e)}")


@router.get("/history")
async def get_chat_history(
    spec_id: uuid.UUID,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    uid = user.get("sub")
    messages = db.query(ChatMessageModel).filter(
        ChatMessageModel.spec_id == str(spec_id),
        ChatMessageModel.user_id == uid
    ).order_by(ChatMessageModel.created_at.asc()).all()
    
    # Format list of messages for the frontend
    formatted = []
    for msg in messages:
        formatted.append({"role": "user", "content": msg.query})
        formatted.append({"role": "assistant", "content": msg.response})
        
    return {"messages": formatted}
