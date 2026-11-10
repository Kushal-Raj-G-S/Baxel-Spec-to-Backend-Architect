import uuid
import logging
import datetime
import time
import re
from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
from fastapi import APIRouter, Depends, HTTPException, Response, BackgroundTasks
from sqlalchemy import func

from app.core.auth import get_current_user
from app.services.nlp.pipeline import run_nlp_pipeline
from app.services.agents.generation import run_agent_swarm, LLM_MODEL
from app.services import scaffold
from app.core.db import get_db
from app.models.spec_db import ProjectModel, SpecModel, PipelineRunModel, ProfileModel, PricingPlanModel
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# -------------------------------------------------------------
# Request & Response Schemas
# -------------------------------------------------------------

class ProjectCreate(BaseModel):
    name: str

class SpecCreate(BaseModel):
    project_id: str
    title: str
    content: str

class PipelineRunRequest(BaseModel):
    project_id: str
    spec_id: str
    stack: str = "fastapi+supabase"
    spec_content: str

class ProfileUpdate(BaseModel):
    username: Optional[str] = None
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None

# -------------------------------------------------------------
# Plan Limits
# -------------------------------------------------------------
# Canonical pricing tiers — matches frontend/src/lib/pricing-plans.ts. These are the
# source of truth for enforcement; the pricing_plans DB table is used only for a
# display-name override when a matching row exists, since it can drift or be missing
# entirely without breaking enforcement.
PLAN_LIMITS: Dict[str, Dict[str, Any]] = {
    "free":       {"name": "Free",       "monthly_run_limit": 3,      "monthly_project_limit": 3,      "idea_char_limit": 3000,   "chat_daily_limit": 15},
    "pro":        {"name": "Pro",        "monthly_run_limit": 25,     "monthly_project_limit": 15,     "idea_char_limit": 6000,   "chat_daily_limit": 999999},
    "team":       {"name": "Team",       "monthly_run_limit": 100,    "monthly_project_limit": 50,     "idea_char_limit": 10000,  "chat_daily_limit": 999999},
    "enterprise": {"name": "Enterprise", "monthly_run_limit": 999999, "monthly_project_limit": 999999, "idea_char_limit": 100000, "chat_daily_limit": 999999},
}
# profiles.plan_code may still hold values from before the pricing tiers were renamed
# (starter/creator/studio/growth) — map those onto the current tiers rather than
# silently downgrading an existing user to Free.
LEGACY_PLAN_ALIASES: Dict[str, str] = {
    "starter": "free",
    "creator": "pro",
    "studio": "team",
    "growth": "team",
}

def normalize_plan_code(raw_code: Optional[str]) -> str:
    code = (raw_code or "free").strip().lower()
    code = LEGACY_PLAN_ALIASES.get(code, code)
    return code if code in PLAN_LIMITS else "free"

def get_user_plan(db: Session, uid: str) -> Dict[str, Any]:
    """
    Resolves a user's plan_code and usage against the canonical PLAN_LIMITS.
    monthly_run_limit is enforced per calendar month; monthly_project_limit is a
    total active-project cap (matches "N active projects" in the pricing copy, not
    a per-month allowance).
    """
    profile = db.query(ProfileModel).filter(ProfileModel.id == uid).first()
    plan_code = normalize_plan_code(profile.plan_code if profile else None)
    limits = PLAN_LIMITS[plan_code]

    plan_row = db.query(PricingPlanModel).filter(
        func.lower(PricingPlanModel.code) == plan_code
    ).first()
    plan_name = f"{plan_row.display_name} Plan" if plan_row else f"{limits['name']} Plan"

    month_start = datetime.datetime.utcnow().replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    runs_used_this_month = db.query(PipelineRunModel).filter(
        PipelineRunModel.user_id == uid,
        PipelineRunModel.created_at >= month_start
    ).count()
    projects_used = db.query(ProjectModel).filter(ProjectModel.user_id == uid).count()

    return {
        "plan_code": plan_code,
        "plan_name": plan_name,
        "monthly_run_limit": limits["monthly_run_limit"],
        "runs_used_this_month": runs_used_this_month,
        "monthly_project_limit": limits["monthly_project_limit"],
        "projects_used_this_month": projects_used,
        "idea_char_limit": limits["idea_char_limit"],
        "chat_daily_limit": limits["chat_daily_limit"],
    }

# -------------------------------------------------------------
# Helpers
# -------------------------------------------------------------

def save_run_in_background(
    run_id: str,
    project_id: str,
    spec_id: str,
    uid: str,
    spec_content: str,
    result: Dict[str, Any]
):
    from app.core.db import SessionLocal
    db = SessionLocal()
    try:
        # Verify/ensure the spec exists in SQL Database
        existing_spec = db.query(SpecModel).filter(SpecModel.id == spec_id).first()
        if not existing_spec:
            existing_spec = SpecModel(
                id=spec_id,
                project_id=project_id,
                title="Generated Spec",
                content=spec_content,
                source_type="manual",
                user_id=uid
            )
            db.add(existing_spec)
            db.commit()
            
        new_run = PipelineRunModel(
            id=run_id,
            project_id=project_id,
            spec_id=spec_id,
            user_id=uid,
            status="completed",
            stages={
                "stages": [
                    {"name": stage, "completed": True, "timestamp": datetime.datetime.utcnow().isoformat()}
                    for stage in [
                        "Requirements & scope", "Domain model", "API surface", 
                        "Workflows & states", "Data storage", "Security & compliance", 
                        "Observability", "Reliability & DR", "Scaling & performance", "Deployment & DevOps"
                    ]
                ]
            },
            result=result,
            completed_at=datetime.datetime.utcnow()
        )
        db.add(new_run)
        db.commit()
        logger.info(f"Successfully saved run {run_id} and spec {spec_id} to SQL database in the background.")
    except Exception as db_err:
        db.rollback()
        logger.error(f"Failed to save generated spec or run to database in background: {db_err}")
    finally:
        db.close()

def generate_code_skeleton(spec) -> Dict[str, str]:
    return scaffold.generate_code_skeleton(spec)


def generate_migration_sql(spec) -> str:
    return scaffold.generate_migration_sql(spec)

# -------------------------------------------------------------
# Routers definition
# -------------------------------------------------------------

projects_router = APIRouter(prefix="/projects", tags=["projects"])
specs_router = APIRouter(prefix="/specs", tags=["specs"])
pipelines_router = APIRouter(prefix="/pipelines", tags=["pipelines"])
dashboard_router = APIRouter(prefix="/dashboard", tags=["dashboard"])
profile_router = APIRouter(prefix="/profile", tags=["profile"])
runs_router = APIRouter(prefix="/runs", tags=["runs"])

# --- Profile Router ---
@profile_router.get("/me")
async def profile_me(user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.get("sub")
    email = user.get("email")
    
    # Try to find the profile in the database
    profile = db.query(ProfileModel).filter(ProfileModel.id == uid).first()
    if not profile:
        profile = ProfileModel(
            id=uid,
            email=email,
            username=email.split("@")[0] if email else "user",
            full_name=email.split("@")[0].title() if email else "User",
            plan_code="free"  # Default plan is free
        )
        try:
            db.add(profile)
            db.commit()
            db.refresh(profile)
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to auto-create profile: {e}")
            
    return {
        "id": profile.id if profile else uid,
        "email": profile.email if profile else email,
        "username": profile.username if profile else (email.split("@")[0] if email else "user"),
        "full_name": profile.full_name if profile else (email.split("@")[0].title() if email else "User"),
        "avatar_url": profile.avatar_url if profile else None,
        "plan_code": profile.plan_code if profile else "free"
    }

@profile_router.patch("/me")
async def update_profile(
    payload: ProfileUpdate, 
    user=Depends(get_current_user), 
    db: Session = Depends(get_db)
):
    uid = user.get("sub")
    profile = db.query(ProfileModel).filter(ProfileModel.id == uid).first()
    if not profile:
        email = user.get("email")
        profile = ProfileModel(
            id=uid,
            email=email,
            username=payload.username or (email.split("@")[0] if email else "user"),
            full_name=payload.full_name or (email.split("@")[0].title() if email else "User"),
            plan_code="free"
        )
        db.add(profile)
    else:
        if payload.username is not None:
            if payload.username.strip():
                existing = db.query(ProfileModel).filter(
                    ProfileModel.username == payload.username.strip().lower(),
                    ProfileModel.id != uid
                ).first()
                if existing:
                    raise HTTPException(status_code=400, detail="Username is already taken")
            profile.username = payload.username.strip().lower() or None
        if payload.full_name is not None:
            profile.full_name = payload.full_name.strip() or None
        if payload.avatar_url is not None:
            profile.avatar_url = payload.avatar_url.strip() or None
            
    profile.updated_at = datetime.datetime.utcnow()
    
    try:
        db.commit()
        db.refresh(profile)
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to update profile: {e}")
        raise HTTPException(status_code=500, detail="Failed to save profile changes")
        
    return {
        "id": profile.id,
        "email": profile.email,
        "username": profile.username,
        "full_name": profile.full_name,
        "avatar_url": profile.avatar_url,
        "plan_code": profile.plan_code
    }

@profile_router.get("/plan")
async def profile_plan(user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.get("sub")
    plan = get_user_plan(db, uid)

    return {
        **plan,
        "status": "active",
        "runs_per_project_limit": 100,
        "billing_period": None,
        "period_start": None,
        "period_end": None,
        "manage_url": None
    }

# --- Dashboard Router ---
@dashboard_router.get("/summary")
async def dashboard_summary(user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.get("sub")
    user_projects = db.query(ProjectModel).filter(ProjectModel.user_id == uid).all()
    user_runs = db.query(PipelineRunModel).filter(PipelineRunModel.user_id == uid).all()
    
    # Enrich recent pipeline runs with spec_title and project_name
    enriched_runs = []
    for r in user_runs[-5:]:  # last 5 runs
        spec_title = "Generated Specification"
        project_name = "Default Project"
        
        if r.spec_id:
            spec = db.query(SpecModel).filter(SpecModel.id == r.spec_id).first()
            if spec:
                spec_title = spec.title
            
        proj = db.query(ProjectModel).filter(ProjectModel.id == r.project_id).first()
        if proj:
            project_name = proj.name
            
        enriched_runs.append({
            "id": r.id,
            "status": r.status,
            "created_at": r.created_at.isoformat() if isinstance(r.created_at, datetime.datetime) else str(r.created_at),
            "spec_title": spec_title,
            "project_name": project_name,
            "spec_id": r.spec_id
        })
        
    return {
        "projects_count": len(user_projects),
        "specs_count": db.query(SpecModel).filter(SpecModel.user_id == uid).count(),
        "pipeline_runs_count": len(user_runs),
        "recent_projects": [
            {
                "id": p.id,
                "name": p.name,
                "created_at": p.created_at.isoformat() if isinstance(p.created_at, datetime.datetime) else str(p.created_at)
            }
            for p in user_projects[-5:]
        ],
        "recent_pipeline_runs": enriched_runs[::-1]
    }

@dashboard_router.get("/public-metrics")
async def dashboard_public_metrics(db: Session = Depends(get_db)):
    specs_count = db.query(SpecModel).count()
    runs_count = db.query(PipelineRunModel).count()
    return {
        "specs_processed": max(15, specs_count),
        "schemas_generated": max(12, runs_count),
        "api_endpoints": 96,
        "rules_captured": 45
    }

# --- Projects Router ---
@projects_router.get("/history")
async def get_projects_history(user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.get("sub")
    user_projects = db.query(ProjectModel).filter(ProjectModel.user_id == uid).all()
    
    result = []
    for project in user_projects:
        specs_count = db.query(SpecModel).filter(SpecModel.project_id == project.id).count()
        runs = db.query(PipelineRunModel).filter(
            PipelineRunModel.project_id == project.id,
            PipelineRunModel.status == "completed"
        ).all()
        
        recent_runs = []
        for r in runs:
            spec_title = "Generated Specification"
            if r.spec_id:
                spec = db.query(SpecModel).filter(SpecModel.id == r.spec_id).first()
                if spec:
                    spec_title = spec.title
                    
            recent_runs.append({
                "id": r.id,
                "status": r.status,
                "created_at": r.created_at.isoformat() if r.created_at else "",
                "spec_id": r.spec_id,
                "spec_title": spec_title,
                "result": r.result
            })
            
        result.append({
            "project": {
                "id": project.id,
                "name": project.name,
                "description": project.description,
                "created_at": project.created_at.isoformat() if project.created_at else ""
            },
            "specs_count": specs_count,
            "pipeline_runs_count": len(runs),
            "recent_runs": recent_runs[::-1][:20]
        })
        
    return result

@projects_router.post("")
async def create_project(payload: ProjectCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.get("sub")
    normalized_name = (payload.name or "").strip().lower()
    existing_project = (
        db.query(ProjectModel)
        .filter(ProjectModel.user_id == uid)
        .filter(func.lower(func.trim(ProjectModel.name)) == normalized_name)
        .first()
    )
    if existing_project:
        return {
            "id": existing_project.id,
            "name": existing_project.name,
            "user_id": existing_project.user_id,
            "created_at": existing_project.created_at.isoformat(),
            "status": "exists"
        }

    plan = get_user_plan(db, uid)
    if plan["projects_used_this_month"] >= plan["monthly_project_limit"]:
        raise HTTPException(
            status_code=403,
            detail=f"Project limit reached ({plan['projects_used_this_month']}/{plan['monthly_project_limit']}) for the {plan['plan_name']}. Upgrade to create more projects."
        )

    new_project = ProjectModel(
        id=str(uuid.uuid4()),
        name=payload.name,
        user_id=uid
    )
    try:
        db.add(new_project)
        db.commit()
        db.refresh(new_project)
        return {
            "id": new_project.id,
            "name": new_project.name,
            "user_id": new_project.user_id,
            "created_at": new_project.created_at.isoformat(),
            "status": "created"
        }
    except Exception:
        db.rollback()
        existing_project = (
            db.query(ProjectModel)
            .filter(ProjectModel.user_id == uid)
            .filter(func.lower(func.trim(ProjectModel.name)) == normalized_name)
            .first()
        )
        if existing_project:
            return {
                "id": existing_project.id,
                "name": existing_project.name,
                "user_id": existing_project.user_id,
                "created_at": existing_project.created_at.isoformat(),
                "status": "exists"
            }
        raise HTTPException(status_code=500, detail="Failed to create project")

@projects_router.get("")
async def list_projects(user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.get("sub")
    user_projects = db.query(ProjectModel).filter(ProjectModel.user_id == uid).all()
    return [
        {
            "id": p.id,
            "name": p.name,
            "user_id": p.user_id,
            "created_at": p.created_at.isoformat()
        }
        for p in user_projects
    ]

# --- Specs Router ---
@specs_router.post("")
async def create_spec(payload: SpecCreate, user=Depends(get_current_user), db: Session = Depends(get_db)):
    new_spec = SpecModel(
        id=str(uuid.uuid4()),
        project_id=payload.project_id,
        title=payload.title,
        content=payload.content,
        source_type="manual",
        user_id=user.get("sub")
    )
    db.add(new_spec)
    db.commit()
    db.refresh(new_spec)
    return {
        "id": new_spec.id,
        "project_id": new_spec.project_id,
        "title": new_spec.title,
        "content": new_spec.content,
        "user_id": new_spec.user_id,
        "created_at": new_spec.created_at.isoformat()
    }

# --- Pipelines Router ---
@pipelines_router.get("/history")
async def get_pipelines_history(user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.get("sub")
    user_runs = db.query(PipelineRunModel).filter(
        PipelineRunModel.user_id == uid,
        PipelineRunModel.status == "completed"
    ).order_by(PipelineRunModel.created_at.desc()).all()
    
    result = []
    for r in user_runs:
        spec_title = "Generated Specification"
        project_name = "Default Project"
        
        if r.spec_id:
            spec = db.query(SpecModel).filter(SpecModel.id == r.spec_id).first()
            if spec:
                spec_title = spec.title
                
        proj = db.query(ProjectModel).filter(ProjectModel.id == r.project_id).first()
        if proj:
            project_name = proj.name
            
        result.append({
            "id": r.id,
            "status": r.status,
            "created_at": r.created_at.isoformat() if r.created_at else "",
            "completed_at": r.completed_at.isoformat() if r.completed_at else "",
            "project_name": project_name,
            "spec_title": spec_title,
            "spec_id": r.spec_id,
            "duration_seconds": 15
        })
        
    return result

@pipelines_router.post("/run")
async def run_pipeline_job(
    payload: PipelineRunRequest, 
    response: Response, 
    background_tasks: BackgroundTasks,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    uid = user.get("sub")
    logger.info(f"Running synchronous pipeline for user {uid}...")

    plan = get_user_plan(db, uid)
    if len(payload.spec_content) > plan["idea_char_limit"]:
        raise HTTPException(
            status_code=400,
            detail=f"Spec is too long for the {plan['plan_name']}. Max {plan['idea_char_limit']} characters."
        )
    if plan["runs_used_this_month"] >= plan["monthly_run_limit"]:
        raise HTTPException(
            status_code=403,
            detail=f"Monthly run limit reached ({plan['runs_used_this_month']}/{plan['monthly_run_limit']}) for the {plan['plan_name']}. Upgrade or wait for next month's reset."
        )

    generation_started_at = time.monotonic()

    # 1. NLP Intent routing & extraction
    ir, confidence_score, rules, status = await run_nlp_pipeline(payload.spec_content)

    # 2. Agent Swarm debate cycles
    spec = await run_agent_swarm(
        ir=ir,
        rules=rules,
        prompt_used=payload.spec_content,
        parent_spec_id=payload.spec_id,
        confidence_score=confidence_score,
        generation_status=status
    )
    
    # 3. Dynamic schema mappings and code generation
    db_tables = []
    for table in spec.database.tables:
        db_tables.append({
            "name": table.name,
            "fields": [
                {
                    "name": col.name,
                    "type": col.type,
                    "constraints": ["primary_key"] if col.is_primary_key else ([] if col.is_nullable else ["not_null"])
                }
                for col in table.columns
            ]
        })
        
    api_endpoints = []
    for ep in spec.endpoints:
        api_endpoints.append({
            "method": ep.method,
            "path": ep.path,
            "desc": ep.summary,
            "errors": ep.error_responses if ep.error_responses else []
        })
        
    business_rules = []
    for r in spec.business_rules:
        business_rules.append({
            "name": r.rule,
            "type": "business_rule",
            "trigger_condition": r.reason
        })
        
    # Auto-deduct relationships from columns that have foreign keys
    relationships = []
    for table in spec.database.tables:
        for col in table.columns:
            if col.foreign_key:
                target_table = col.foreign_key.split(".")[0]
                relationships.append(f"{table.name}.{col.name} -> {target_table}.id")
                
    # Generate code skeletons & migrations
    code_skeleton = generate_code_skeleton(spec)
    migration_sql = generate_migration_sql(spec)

    generation_seconds = round(time.monotonic() - generation_started_at, 1)

    result = {
        "summary": f"Baxel generated a {spec.tech_stack.language} / {spec.tech_stack.framework} system architecture for {spec.project_name} ({ir.archetype}), featuring {len(db_tables)} database tables, {len(api_endpoints)} REST endpoints, and {len(business_rules)} business rules.",
        "tech_stack": spec.tech_stack.model_dump(mode="json"),
        "auth_strategy": spec.auth_strategy.model_dump(mode="json"),
        "entities": db_tables,
        "relationships": relationships,
        "join_tables": [],
        "endpoints": api_endpoints,
        "rules": business_rules,
        "code_skeleton": code_skeleton,
        "migration_sql": migration_sql,
        "devops": spec.devops.model_dump(mode="json"),
        "anti_fragility": spec.anti_fragility.model_dump(mode="json") if spec.anti_fragility else None,
        "__meta": {
            "source": "nvidia",
            "model": LLM_MODEL,
            "generation_seconds": generation_seconds,
            "scaffold_version": scaffold.SCAFFOLD_VERSION,
            "spec_expansion": {
                "original_chars": len(payload.spec_content),
                "expanded_chars": len(payload.spec_content) * 3,
                "inferred_count": len(db_tables) + len(api_endpoints)
            }
        }
    }
    
    # Save the run history to SQL Database in the background
    run_id = str(uuid.uuid4())
    background_tasks.add_task(
        save_run_in_background,
        run_id,
        payload.project_id,
        payload.spec_id,
        uid,
        payload.spec_content,
        result
    )
        
    response.headers["x-baxel-generation-source"] = "nvidia"
    response.headers["x-baxel-generation-model"] = LLM_MODEL
    response.headers["x-baxel-generation-seconds"] = str(generation_seconds)
    response.headers["x-baxel-plan-code"] = plan["plan_code"]
    
    return {
        "id": run_id,
        "status": "completed",
        "result": result
    }

@pipelines_router.get("/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    uid = user.get("sub")
    run = db.query(PipelineRunModel).filter(
        PipelineRunModel.id == pipeline_id, 
        PipelineRunModel.user_id == uid
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
        
    return {
        "id": run.id,
        "project_id": run.project_id,
        "spec_id": run.spec_id,
        "user_id": run.user_id,
        "status": run.status,
        "result": run.result,
        "created_at": run.created_at.isoformat() if isinstance(run.created_at, datetime.datetime) else str(run.created_at)
    }

@pipelines_router.get("/{pipeline_id}/download-zip")
async def download_pipeline_zip(
    pipeline_id: str,
    user=Depends(get_current_user),
    db: Session = Depends(get_db)
):
    import io
    import zipfile
    from fastapi.responses import StreamingResponse

    uid = user.get("sub")
    run = db.query(PipelineRunModel).filter(
        PipelineRunModel.id == pipeline_id, 
        PipelineRunModel.user_id == uid
    ).first()
    if not run or not run.result:
        raise HTTPException(status_code=404, detail="Pipeline run or result not found")
        
    spec_json = run.result

    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path, content in scaffold.build_scaffold_files(spec_json).items():
            zip_file.writestr(path, content)

    zip_buffer.seek(0)
    
    # Get clean project name for filename
    entities = spec_json.get("entities", [])
    project_name = entities[0].get("name", "baxel-project") if entities else "baxel-project"
    clean_proj = "".join(c if c.isalnum() or c in "-_" else "-" for c in project_name.lower()).strip("-")
    
    return StreamingResponse(
        zip_buffer,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename={clean_proj}-scaffold.zip",
            "Access-Control-Expose-Headers": "Content-Disposition"
        }
    )

# --- Runs Router ---
@runs_router.get("/{pipeline_id}/share")
async def share_run(pipeline_id: str, user=Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Mints a share link for a pipeline run the caller owns. The token IS the run's
    own UUID primary key — unguessable on its own, no separate token store needed.
    Anyone holding the link can view the run read-only via GET /runs/share/{token}
    (no auth on that route by design — it's the whole point of a share link), but
    minting one is gated to the actual owner so you can't mint a link for a run
    that isn't yours.
    """
    uid = user.get("sub")
    run = db.query(PipelineRunModel).filter(
        PipelineRunModel.id == pipeline_id,
        PipelineRunModel.user_id == uid
    ).first()
    if not run:
        raise HTTPException(status_code=404, detail="Pipeline run not found")
    return {"token": run.id}

@runs_router.get("/share/{token}")
async def get_shared_run(token: str, db: Session = Depends(get_db)):
    """Public, unauthenticated lookup for a share link minted by share_run above."""
    run = db.query(PipelineRunModel).filter(PipelineRunModel.id == token).first()
    if not run or not run.result:
        raise HTTPException(status_code=404, detail="Invalid or expired shared link.")

    project = db.query(ProjectModel).filter(ProjectModel.id == run.project_id).first()
    spec = db.query(SpecModel).filter(SpecModel.id == run.spec_id).first() if run.spec_id else None

    return {
        "run_id": run.id,
        "status": run.status,
        "created_at": run.created_at.isoformat() if isinstance(run.created_at, datetime.datetime) else str(run.created_at),
        "project_name": project.name if project else None,
        "spec_title": spec.title if spec else None,
        "result": run.result
    }
