from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends
from pydantic import BaseModel, Field
from typing import Optional, Any
from sqlalchemy.orm import Session
import uuid

from app.core.db import get_db
from app.core.auth import get_current_user
from app.services.generation_service import run_generation_pipeline, generation_status_db

router = APIRouter()

class GenerateRequest(BaseModel):
    prompt: str = Field(..., description="The user prompt describing the desired architecture")
    parent_spec_id: Optional[str] = Field(None, description="Optional parent spec ID to iterate from")

class GenerateResponse(BaseModel):
    spec_id: uuid.UUID
    status: str

@router.post("/generate", response_model=GenerateResponse)
async def generate_spec(
    request: GenerateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    user=Depends(get_current_user)
):
    spec_id = uuid.uuid4()
    uid = user.get("sub")

    # Run the NLP + RAG + Agents Swarm in background
    background_tasks.add_task(
        run_generation_pipeline,
        spec_id,
        request.prompt,
        request.parent_spec_id,
        db,
        uid
    )

    return GenerateResponse(spec_id=spec_id, status="processing")

@router.get("/status/{spec_id}")
async def get_status(spec_id: uuid.UUID, user=Depends(get_current_user)):
    spec_id_str = str(spec_id)
    if spec_id_str not in generation_status_db:
        raise HTTPException(status_code=404, detail="Spec ID not found or expired.")

    return generation_status_db[spec_id_str]
