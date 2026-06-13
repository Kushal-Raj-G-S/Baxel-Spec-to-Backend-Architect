import uuid
import logging
from sqlalchemy.orm import Session
from app.models.spec_db import ProjectModel, SpecModel, PipelineRunModel
import datetime
from app.services.nlp.pipeline import run_nlp_pipeline
from app.services.agents.generation import run_agent_swarm

logger = logging.getLogger(__name__)

# Global in-memory generation status storage for status tracking endpoint
generation_status_db = {}

async def run_generation_pipeline(
    spec_id: uuid.UUID, 
    prompt: str, 
    parent_spec_id: str, 
    db_session: Session
):
    """
    Coordinates the entire generation process (NLP, RAG, Agents) asynchronously.
    Saves the final generated JSON to the SQL database.
    """
    spec_id_str = str(spec_id)
    generation_status_db[spec_id_str] = {
        "status": "processing",
        "progress": 10,
        "current_stage": "semantic_routing",
        "error": None
    }
    
    try:
        # Phase 1 & 2: NLP Intent Routing, NER, synonym clustering, and RAG retrieval
        logger.info(f"[{spec_id_str}] Phase 1 & 2: Executing NLP & RAG pipelines...")
        ir, confidence_score, rules, status = await run_nlp_pipeline(prompt)
        
        generation_status_db[spec_id_str].update({
            "progress": 50,
            "current_stage": "agent_debate_swarm"
        })
        
        # Phase 3: Agentic Generation & Debate
        logger.info(f"[{spec_id_str}] Phase 3: Executing Agent swarm debate...")
        spec = await run_agent_swarm(
            ir=ir,
            rules=rules,
            prompt_used=prompt,
            parent_spec_id=parent_spec_id,
            confidence_score=confidence_score,
            generation_status=status
        )
        
        # Ensure we have a default project
        project = db_session.query(ProjectModel).first()
        if not project:
            project = ProjectModel(
                id=str(uuid.uuid4()),
                name="Default Project",
                user_id=None
            )
            db_session.add(project)
            db_session.commit()
            db_session.refresh(project)
            
        # Save output to Database
        logger.info(f"[{spec_id_str}] Saving generated output to Database...")
        db_spec = SpecModel(
            id=spec_id_str,
            project_id=project.id,
            title="Generated Spec",
            content=prompt,
            source_type="api",
            user_id=None
        )
        db_session.add(db_spec)
        
        # Save pipeline run record
        db_run = PipelineRunModel(
            id=str(uuid.uuid4()),
            project_id=project.id,
            spec_id=spec_id_str,
            status="completed",
            stages={"stages": []},
            result=spec.model_dump(),
            completed_at=datetime.datetime.utcnow(),
            user_id=None
        )
        db_session.add(db_run)
        db_session.commit()
        
        generation_status_db[spec_id_str].update({
            "status": "completed",
            "progress": 100,
            "current_stage": "completed",
            "result": spec.model_dump()
        })
        logger.info(f"[{spec_id_str}] Generation process completed successfully.")
        
    except Exception as e:
        logger.error(f"[{spec_id_str}] Generation process failed: {e}", exc_info=True)
        generation_status_db[spec_id_str].update({
            "status": "failed",
            "progress": 100,
            "current_stage": "failed",
            "error": str(e)
        })
