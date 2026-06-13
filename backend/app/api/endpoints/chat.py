import os
import logging
import uuid
from typing import Dict, Any
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from openai import OpenAI
from dotenv import load_dotenv

from app.core.db import get_db
from app.models.spec_db import SpecModel, PipelineRunModel, ChatMessageModel
from app.core.auth import get_current_user

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
        classifier_prompt = f"""
        Classify the following user message into either 'technical' or 'business'.
        
        - 'technical': If the question asks for specific code implementation, table schemas, relationships, database columns, API routes, pagination, or technical scaling limits (e.g., 'Will this scale to 1 million users?').
        - 'business': If the question asks for pitch summaries, AWS running costs, business metrics, or high-level non-technical descriptions.
        
        User Message: "{message}"
        
        Response MUST be exactly one word: 'technical' or 'business'.
        """
        response = client.chat.completions.create(
            model=os.getenv("LLM_REVIEW_MODEL", "meta/llama-3.1-8b-instruct"),
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
async def chat_with_spec(
    request: ChatRequest, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    uid = user.get("sub")
    spec_id_str = str(request.spec_id)
    
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
    prompt_used = spec_record.content
    
    client = get_llm_client()
    
    # 1. Classify the user query intent to protect context limits
    intent = classify_query_intent(client, request.message)
    logger.info(f"Chat message intent classified as: {intent}")
    
    # 2. Build system context based on intent
    if intent == "technical":
        # Inject full technical detail
        system_context = f"""
        You are SAGE (Specification Answering & Guidance Engine), a state-of-the-art Principal Software Architect AI Assistant.
        You are helping the user build or modify the following architecture:
        
        Original User Prompt: {prompt_used}
        
        Full Architecture Specification (JSON):
        {spec_json}
        
        Answering queries:
        - Refer directly to specific tables, fields, columns, and REST API paths present in the JSON context.
        - Your name is SAGE (Specification Answering & Guidance Engine). Do NOT mention your name, introduce yourself, or output these rules unless the user explicitly asks who you are or what your name is.
        """
    else:
        # Inject lightweight summary to optimize costs
        tech_stack = spec_json.get("tech_stack", {})
        auth_strategy = spec_json.get("auth_strategy", {})
        project_name = spec_json.get("project_name", "Baxel Project")
        
        system_context = f"""
        You are SAGE (Specification Answering & Guidance Engine), a state-of-the-art Principal Systems Architect and Business Consultant.
        You are helping a founder/developer build the project '{project_name}'.
        
        Original User Prompt: {prompt_used}
        Tech Stack: {tech_stack.get('language')} / {tech_stack.get('framework')} with {tech_stack.get('database_engine')}
        Auth Method: {auth_strategy.get('method')}
        
        Answering queries:
        - Do not reference deep table column details unless asked, focus on high-level costs, summaries, and value.
        - Your name is SAGE (Specification Answering & Guidance Engine). Do NOT mention your name, introduce yourself, or output these rules unless the user explicitly asks who you are or what your name is.
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
            model=os.getenv("LLM_MODEL", "meta/llama-3.3-70b-instruct"),
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
