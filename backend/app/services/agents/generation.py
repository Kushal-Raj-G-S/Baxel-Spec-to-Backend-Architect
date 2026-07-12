import os
import logging
import asyncio
from typing import List, Dict, Any, Tuple
from openai import OpenAI
import instructor
from dotenv import load_dotenv
from pydantic import BaseModel

from app.schemas.spec import (
    GeneratedArchitectureSpec, 
    ReviewResult, 
    IntermediateRepresentation,
    SpecMetadata,
    TechStack,
    AuthStrategy,
    DatabaseSchema,
    TableSchema,
    ColumnSchema,
    EndpointSchema,
    BusinessRule,
    DevOpsSetup,
    SpiceLayer,
    ChaosFailureScenario,
    AntiFragilityHardening
)

from pathlib import Path

# Load environment variables
load_dotenv(override=True)

logger = logging.getLogger(__name__)


class _DatabaseSpec(BaseModel):
    project_name: str
    tech_stack: TechStack
    auth_strategy: AuthStrategy
    database: DatabaseSchema


class _EndpointsSpec(BaseModel):
    endpoints: List[EndpointSchema]


class _BusinessRulesSpec(BaseModel):
    business_rules: List[BusinessRule]


class _DevOpsSpec(BaseModel):
    devops: DevOpsSetup


class _SpiceSpec(BaseModel):
    spice: SpiceLayer


class _ResilienceSpec(BaseModel):
    anti_fragility: AntiFragilityHardening



ENUM_VALUE_HINTS: Dict[str, List[str]] = {
    "providers.verification_status": ["draft", "pending_verification", "verified", "live", "rejected", "suspended"],
    "providers.subscription_tier": ["free", "pro", "business", "enterprise"],
    "providers.service_area_type": ["radius", "zip_list", "unlimited"],
    "bookings.status": ["pending", "confirmed", "in_progress", "completed", "cancelled", "disputed", "no_show"],
    "payments.payment_status": ["pending", "captured", "released", "refunded", "failed"],
    "payments.payout_status": ["pending", "released", "failed"],
    "disputes.resolution_status": ["open", "under_review", "resolved", "rejected", "closed"],
    "messages.type": ["text", "photo", "video"],
}


def _normalize_generated_spec(spec: GeneratedArchitectureSpec) -> GeneratedArchitectureSpec:
    """Apply deterministic cleanup so known state fields and error codes are structurally valid."""
    for table in spec.database.tables:
        for column in table.columns:
            # Clean up foreign key format
            if column.foreign_key:
                import re
                fk = column.foreign_key.strip()
                fk_match = re.match(r"^([\w_-]+)\(?([\w_-]*)\)?(?:\(?([\w_-]*)\)?)?$", fk)
                if fk_match:
                    tbl = fk_match.group(1)
                    col = fk_match.group(2) or "id"
                    column.foreign_key = f"{tbl}.{col}"
                else:
                    column.foreign_key = fk.replace("(", ".").replace(")", "").replace("..", ".")

            hint_key = f"{table.name}.{column.name}"
            if hint_key in ENUM_VALUE_HINTS:
                column.type = "Enum"
                if not column.enum_values:
                    column.enum_values = ENUM_VALUE_HINTS[hint_key]
            elif column.type.lower() == "enum" and not column.enum_values:
                guessed_values = ENUM_VALUE_HINTS.get(hint_key) or ENUM_VALUE_HINTS.get(column.name)
                if guessed_values:
                    column.enum_values = guessed_values

    for endpoint in spec.endpoints:
        cleaned_errors: List[str] = []
        for error_code in endpoint.error_responses or []:
            digits = "".join(character for character in str(error_code) if character.isdigit())
            if len(digits) == 3:
                cleaned_errors.append(digits)
        endpoint.error_responses = cleaned_errors or None

    return spec

# LLM Configurations
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_MODEL = "openai/gpt-oss-20b"
# Lightweight model for fast review agents (DBA, Security, PM) — much lower latency
LLM_REVIEW_MODEL = "meta/llama-3.1-8b-instruct"

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

def get_instructor_client() -> Tuple[Any, bool]:
    """
    Initializes and returns the instructor client.
    Returns (client, is_mock). If API key is missing, returns a mock indicator.
    
    IMPORTANT: timeout=360 is set at the HTTP level so the underlying socket
    gives the 70B model enough time to generate a full spec (~180-300s typical).
    Without this, the socket would close before the model finishes.
    """
    api_key = _load_api_key()
    if not api_key:
        logger.warning("NVIDIA_API_KEY not found. Falling back to local Mock Generator.")
        return None, True
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=LLM_BASE_URL,
            timeout=360.0  # 6-minute socket timeout — gives 70B model full time to respond
        )
        instructor_client = instructor.from_openai(client, mode=instructor.Mode.JSON)
        return instructor_client, False
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}. Falling back to mock.")
        return None, True

# -------------------------------------------------------------
# Agent Definitions
# -------------------------------------------------------------

async def _generate_database_spec(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    rules: List[str],
    feedback_history: List[str] = None
) -> _DatabaseSpec:
    logger.info(f"[Swarm] Database Spec generation starting with model: {LLM_MODEL}")
    entity_list = ", ".join(ir.entities[:12]) if ir.entities else "none"
    actor_list = ", ".join(ir.actors[:10]) if ir.actors else "none"
    integration_list = ", ".join(ir.implied_integrations[:10]) if ir.implied_integrations else "none"
    
    prompt = f"""
    You are a Principal Software Architect specializing in relational database design.
    Output only JSON matching the requested schema.
    Keep field values concise and do not add markdown or filler.

    User Spec Excerpt:
    {spec_excerpt}

    NLP Context:
    - Archetype: {ir.archetype}
    - Entities: {entity_list}
    - Actors: {actor_list}
    - Integrations: {integration_list}

    Rules:
    {chr(10).join([f'- {r}' for r in rules])}

    Task: Generate project_name, tech_stack, auth_strategy, and database schema.
    Ensure every table has a primary key. Enforce foreign keys when referencing other tables.
    For stateful columns (e.g. status, verification, payment/booking status), use Enum and define enum_values.

    Before finalizing, double check the user's spec excerpt to ensure you have modeled all key domain concepts as real tables, especially any payment models, workflows, or custom domain entity relationships mentioned in the requirements. Do not invent marketplace constructs (e.g., commissions, independent provider reviews, buyer/seller escrows) unless explicitly mentioned in the spec. Do not omit a subsystem just because it wasn't in the first few sentences of the excerpt — read the whole thing.
    """
    if feedback_history:
        prompt += f"\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_DatabaseSpec,
            max_retries=0,
            max_tokens=16384,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": "Output only compact JSON matching schema."},
                {"role": "user", "content": prompt}
            ]
        )
    )


async def _generate_endpoints_spec(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    db_spec: _DatabaseSpec,
    rules: List[str],
    feedback_history: List[str] = None
) -> _EndpointsSpec:
    logger.info(f"[Swarm] Endpoints Spec generation starting with model: {LLM_MODEL}")
    table_names = ", ".join([t.name for t in db_spec.database.tables])
    prompt = f"""
    You are a Principal Software Architect specializing in RESTful API design.
    Output only JSON matching the requested schema.

    User Spec Excerpt:
    {spec_excerpt}

    Database context (existing tables):
    {table_names}

    Task: Generate only API endpoints matching the database tables.
    CRITICAL CONSTRAINT: You MUST only reference tables present in the database context list: {table_names}. Do not invent endpoints for subsystems that have no tables in this list.
    
    1. Define a complete REST contract matching the database tables and authentication strategy. Ensure endpoints indicate whether they are protected. Keep request/response schemas clean.
    2. For any table with a status or state column, include dedicated transition endpoints (e.g. PATCH /bookings/{id}/status) rather than only exposing status as an editable field in PUT.
    3. Include specific action endpoints implied by the business requirements (e.g. verification pipelines, payout execution, refund processing, dispute creation).
    4. Populate error_responses with realistic 3-digit HTTP status codes (e.g. ['400', '401', '403', '404', '409']) as appropriate — do not leave error_responses empty.
    """
    if feedback_history:
        prompt += f"\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_EndpointsSpec,
            max_retries=0,
            max_tokens=16384,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": "Output only compact JSON matching schema."},
                {"role": "user", "content": prompt}
            ]
        )
    )


async def _generate_business_rules_spec(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    db_spec: _DatabaseSpec,
    rules: List[str],
    feedback_history: List[str] = None
) -> _BusinessRulesSpec:
    logger.info(f"[Swarm] Business Rules Spec generation starting with model: {LLM_MODEL}")
    table_names = ", ".join([t.name for t in db_spec.database.tables])
    prompt = f"""
    You are a Principal Software Architect.
    Output only JSON matching the requested schema.

    User Spec Excerpt:
    {spec_excerpt}

    Database tables:
    {table_names}

    Task: Generate only business_rules list matching the database.
    CRITICAL CONSTRAINT: You MUST only reference tables and concepts present in the database context list: {table_names}. Do not invent business rules for subsystems that have no tables in this list.
    Provide specific constraints and logical checks (e.g. data validation, state transitions)
    derived from the user prompt and rules.
    """
    if feedback_history:
        prompt += f"\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_BusinessRulesSpec,
            max_tokens=16384,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": "Output only compact JSON matching schema."},
                {"role": "user", "content": prompt}
            ]
        )
    )


async def _generate_devops_spec(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    db_spec: _DatabaseSpec,
    rules: List[str],
    feedback_history: List[str] = None
) -> _DevOpsSpec:
    logger.info(f"[Swarm] DevOps Spec generation starting with model: {LLM_MODEL}")
    tech_stack_desc = f"Language: {db_spec.tech_stack.language}, Framework: {db_spec.tech_stack.framework}, Database: {db_spec.tech_stack.database_engine}"
    prompt = f"""
    You are a DevOps and Cloud Infrastructure Engineer.
    Output only JSON matching the requested schema.

    Tech Stack:
    {tech_stack_desc}

    Task: Generate only devops setup details.
    1. A list of key environment variables keys needed for this stack.
    2. A complete, production-ready Dockerfile for this tech stack.
    3. An optional docker-compose.yml including database, cache (Redis), and backend service configured properly.
    """
    if feedback_history:
        prompt += f"\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_DevOpsSpec,
            max_tokens=16384,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": "Output only compact JSON matching schema."},
                {"role": "user", "content": prompt}
            ]
        )
    )


async def _generate_spice_spec(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    db_spec: _DatabaseSpec,
    feedback_history: List[str] = None
) -> _SpiceSpec:
    logger.info(f"[Swarm] Spice Spec generation starting with model: {LLM_MODEL}")
    prompt = f"""
    You are a Principal Software Architect and Tech Lead.
    Output only JSON matching the requested schema.

    Project Name: {db_spec.project_name}
    Tech Stack: {db_spec.tech_stack.language} / {db_spec.tech_stack.framework} / {db_spec.tech_stack.database_engine}

    Task: Generate only the spice layer.
    - devils_advocate: Warning about failure points or trade-offs at extreme scale.
    - design_rationale: Deep explanation of why this stack fits the archetype.
    - estimated_time_saved_hours: Value estimation.
    """
    if feedback_history:
        prompt += f"\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_SpiceSpec,
            max_retries=0,
            max_tokens=16384,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": "Output only compact JSON matching schema."},
                {"role": "user", "content": prompt}
            ]
        )
    )


async def _generate_resilience_spec(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    db_spec: _DatabaseSpec,
    rules: List[str],
    feedback_history: List[str] = None
) -> _ResilienceSpec:
    logger.info(f"[Swarm] Resilience Spec generation starting with model: {LLM_MODEL}")
    table_names = ", ".join([t.name for t in db_spec.database.tables])
    prompt = f"""
    You are a Chaos Engineering and Reliability Architect.
    Output only JSON matching the requested schema.

    Project: {db_spec.project_name}
    Archetype: {ir.archetype}
    Tables: {table_names}

    Task: Generate only the anti_fragility plan.
    CRITICAL CONSTRAINT: You MUST invent failure scenarios and checklists that are 100% relevant to this project's domains and stack ({ir.archetype}).
    Do NOT copy or use the examples from the Pydantic schema descriptions (like Acoustic Telemetry or Ledger DB Lock). Choose realistic failure scenarios relevant to database locks, payment failures, API load spikes, or websocket drops.
    - resilience_rating: Letter grade (A+ to F).
    - critical_vulnerabilities: single points of failure.
    - chaos_scenarios: 3 detailed production failure scenarios and mitigations.
    - hardening_checklist: 4-step hardening checklist.
    """
    if feedback_history:
        prompt += f"\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_ResilienceSpec,
            max_tokens=16384,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": "Output only compact JSON matching schema."},
                {"role": "user", "content": prompt}
            ]
        )
    )


def _merge_specs(
    db_spec: Any,
    ep_spec: Any,
    br_spec: Any,
    do_spec: Any,
    sp_spec: Any,
    res_spec: Any,
    ir: IntermediateRepresentation,
    prompt_used: str
) -> GeneratedArchitectureSpec:
    # If DB Spec itself failed/exception, raise it because DB is critical
    if isinstance(db_spec, Exception):
        logger.error(f"Critical Core Spec Generation failed: {db_spec}")
        raise db_spec

    # Extract Endpoints (with fallback)
    endpoints = []
    if isinstance(ep_spec, Exception):
        logger.warning("Endpoints generation failed. Using fallback REST endpoints.", exc_info=ep_spec)
        for table in db_spec.database.tables:
            endpoints.append(
                EndpointSchema(
                    method="GET",
                    path=f"/api/v1/{table.name}",
                    summary=f"Get list of {table.name}",
                    is_protected=True,
                    response_payload_schema="items: array"
                )
            )
            endpoints.append(
                EndpointSchema(
                    method="POST",
                    path=f"/api/v1/{table.name}",
                    summary=f"Create a new {table.name[:-1] if table.name.endswith('s') else table.name}",
                    is_protected=True,
                    request_payload_schema="data: object",
                    response_payload_schema="id: string"
                )
            )
    else:
        endpoints = ep_spec.endpoints

    # Extract Business Rules (with fallback)
    business_rules = []
    if isinstance(br_spec, Exception):
        logger.warning("Business Rules generation failed. Using generic rule.", exc_info=br_spec)
        business_rules.append(
            BusinessRule(
                rule="Verify tenant data isolation on every transactional query",
                reason="Mandatory system rule for multi-tenant isolation."
            )
        )
    else:
        business_rules = br_spec.business_rules

    # Extract DevOps (with fallback)
    devops = None
    if isinstance(do_spec, Exception):
        logger.warning("DevOps generation failed. Using fallback Docker setup.", exc_info=do_spec)
        devops = DevOpsSetup(
            environment_variables=["DATABASE_URL", "PORT"],
            dockerfile_content="FROM python:3.11\nWORKDIR /app\nCOPY . .\nCMD [\"python\", \"main.py\"]"
        )
    else:
        devops = do_spec.devops

    # Extract Spice (with fallback)
    spice = None
    if isinstance(sp_spec, Exception):
        logger.warning("Spice generation failed. Using fallback design rationale.", exc_info=sp_spec)
        spice = SpiceLayer(
            devils_advocate="High concurrent connections could exhaust DB pool size. Ensure pool bounds are explicit.",
            design_rationale="Selected stack is tailored for microservice scalability.",
            estimated_time_saved_hours=8
        )
    else:
        spice = sp_spec.spice

    # Create Merged spec shell
    merged_spec_stub = GeneratedArchitectureSpec(
        metadata=SpecMetadata(
            version="1.0.0",
            parent_spec_id=None,
            created_at="2025-11-03T12:00:00Z",
            prompt_used=prompt_used[:200],
            confidence_score=None,
            generation_status="complete"
        ),
        project_name=db_spec.project_name,
        tech_stack=db_spec.tech_stack,
        auth_strategy=db_spec.auth_strategy,
        database=db_spec.database,
        endpoints=endpoints,
        business_rules=business_rules,
        devops=devops,
        spice=spice,
        anti_fragility=None
    )

    # Extract Resilience / Anti-Fragility (with fallback)
    anti_fragility = None
    if isinstance(res_spec, Exception):
        logger.warning("Resilience generation failed. Using rule-based fallback.", exc_info=res_spec)
        anti_fragility = generate_fallback_anti_fragility(merged_spec_stub, ir)
    else:
        anti_fragility = res_spec.anti_fragility

    merged_spec_stub.anti_fragility = anti_fragility
    return _normalize_generated_spec(merged_spec_stub)


async def run_architect_agent(
    client: Any,
    ir: IntermediateRepresentation,
    rules: List[str],
    prompt_used: str,
    feedback_history: List[str] = None
) -> GeneratedArchitectureSpec:
    """
    Principal Architect Agent: Drafts or refines the system design specification.
    Uses Phase 1A Database generation, followed by Phase 1B concurrent fan-out content generation.
    """
    logger.info("Principal Architect drafting system design using parallel hybrid flow...")
    
    # Truncate input spec to keep the architect prompt compact.
    MAX_SPEC_CHARS = 9000
    spec_excerpt = prompt_used[:MAX_SPEC_CHARS]
    if len(prompt_used) > MAX_SPEC_CHARS:
        spec_excerpt += f"\n[...{len(prompt_used) - MAX_SPEC_CHARS} chars truncated...]"
        logger.info(f"Spec truncated from {len(prompt_used)} to {MAX_SPEC_CHARS} chars for architect prompt.")
    
    loop = asyncio.get_running_loop()

    # ── Phase 1A: Core Database Spec (Call 1)
    logger.info("[Swarm] Phase 1A — Generating core Database spec...")
    db_spec = await _generate_database_spec(
        client, loop, spec_excerpt, ir, rules, feedback_history
    )
    logger.info("[Swarm] Phase 1A complete — core Database spec received.")

    # ── Phase 1B: Concurrent Content Generation (Calls 2-6)
    logger.info("[Swarm] Phase 1B — Triggering parallel generation tasks for endpoints, business rules, devops, spice, and resilience...")
    tasks = [
        _generate_endpoints_spec(client, loop, spec_excerpt, ir, db_spec, rules, feedback_history),
        _generate_business_rules_spec(client, loop, spec_excerpt, ir, db_spec, rules, feedback_history),
        _generate_devops_spec(client, loop, spec_excerpt, ir, db_spec, rules, feedback_history),
        _generate_spice_spec(client, loop, spec_excerpt, ir, db_spec, feedback_history),
        _generate_resilience_spec(client, loop, spec_excerpt, ir, db_spec, rules, feedback_history)
    ]

    content_results = await asyncio.gather(*tasks, return_exceptions=True)
    ep_spec, br_spec, do_spec, sp_spec, res_spec = content_results
    logger.info("[Swarm] Phase 1B complete — all parallel generation tasks returned.")

    # ── Phase 1C: Merging Specs into final GeneratedArchitectureSpec
    spec = _merge_specs(
        db_spec, ep_spec, br_spec, do_spec, sp_spec, res_spec, ir, prompt_used
    )
    
    return spec

async def run_dba_agent(client: Any, database: DatabaseSchema, rules: List[str]) -> ReviewResult:
    """
    DBA Review Agent: Checks database schema for performance, relations, and isolation.
    Uses a fast lightweight model for low latency.
    """
    logger.info("DBA Agent reviewing database schema...")
    # Send compact table names + column count only to minimize tokens
    compact_schema = ", ".join(
        [f"{t.name}({len(t.columns)} cols)" for t in database.tables]
    )
    rules_str = "; ".join(rules[:5])  # Only top 5 rules to reduce prompt size
    prompt = f"""Review this DB schema for a software project. Tables: {compact_schema}. Rules: {rules_str}. Check: primary keys, foreign keys, tenant isolation. Output ReviewResult with passed=True if acceptable."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_REVIEW_MODEL,
            response_model=ReviewResult,
            max_tokens=400,  # ReviewResult is small: just passed + issues list
            messages=[
                {"role": "system", "content": "You are a DBA review agent. Be concise. Output ReviewResult JSON."},
                {"role": "user", "content": prompt}
            ]
        )
    )

async def run_security_agent(client: Any, endpoints: List[EndpointSchema], rules: List[str]) -> ReviewResult:
    """
    Security Review Agent: Checks API routes for authentication and vulnerability rules.
    Uses a fast lightweight model for low latency.
    """
    logger.info("Security Agent reviewing API endpoints...")
    # Compact: only list unprotected write endpoints as a concern flag
    unprotected_writes = [f"{e.method} {e.path}" for e in endpoints if not e.is_protected and e.method in ("POST", "PUT", "DELETE", "PATCH")]
    total = len(endpoints)
    prompt = f"""Review {total} API endpoints for security. Unprotected write endpoints: {unprotected_writes or 'None'}. Are write/delete actions properly protected? Output ReviewResult JSON with passed=True if acceptable."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_REVIEW_MODEL,
            response_model=ReviewResult,
            max_tokens=400,  # ReviewResult is small: just passed + issues list
            messages=[
                {"role": "system", "content": "You are a Security auditor agent. Be concise. Output ReviewResult JSON."},
                {"role": "user", "content": prompt}
            ]
        )
    )

async def run_pm_agent(client: Any, spec: GeneratedArchitectureSpec, prompt_used: str) -> ReviewResult:
    """
    PM Review Agent: Assures the product meets the user's business requirements.
    Uses a fast lightweight model with a compact spec summary for low latency.
    """
    logger.info("Product Manager reviewing spec against requirements...")
    # Compact spec summary: project name, table names, endpoint paths only
    table_names = ", ".join([t.name for t in spec.database.tables])
    endpoint_paths = ", ".join([f"{e.method} {e.path}" for e in spec.endpoints[:20]])  # cap at 20
    user_prompt_snippet = prompt_used[:500]  # cap to 500 chars
    prompt = f"""Check if the generated spec meets user requirements.
User requirements (excerpt): {user_prompt_snippet}
Generated tables: {table_names}
Generated endpoints: {endpoint_paths}
Are the key features covered? Output ReviewResult JSON with passed=True if acceptable."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_REVIEW_MODEL,
            response_model=ReviewResult,
            max_tokens=400,  # ReviewResult is small: just passed + issues list
            messages=[
                {"role": "system", "content": "You are a PM review agent. Be concise. Output ReviewResult JSON."},
                {"role": "user", "content": prompt}
            ]
        )
    )

async def run_anti_fragility_agent(
    client: Any,
    spec: GeneratedArchitectureSpec,
    ir: IntermediateRepresentation
) -> AntiFragilityHardening:
    """
    Chaos Engineering & Anti-Fragility Simulation Agent:
    Simulates production failures on the generated architecture and creates a hardening plan.
    """
    logger.info("Anti-Fragility Agent running chaos simulations...")
    
    # Compact schema: table names + endpoint paths only — avoids massive token cost
    compact_tables = ", ".join([f"{t.name}({len(t.columns)} cols)" for t in spec.database.tables])
    compact_endpoints = ", ".join([f"{e.method} {e.path}" for e in spec.endpoints[:25]])
    
    prompt = f"""You are an expert Chaos Engineering & Reliability Architect.

System context:
- Archetype: {ir.archetype}
- Project: {spec.project_name}
- Tables: {compact_tables}
- Endpoints: {compact_endpoints}

Tasks:
1. Assign an overall Resilience Rating (A+ to F).
2. Identify 2-3 single points of failure under peak load.
3. Simulate exactly 3 production failure scenarios with mitigation strategies.
4. Provide a 4-step hardening checklist.

Output a structured AntiFragilityHardening object."""
    
    loop = asyncio.get_running_loop()
    
    # Run in executor to prevent blocking
    # Uses LLM_REVIEW_MODEL (8B) since compact prompt is sufficient for structured chaos output
    result = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_REVIEW_MODEL,
            response_model=AntiFragilityHardening,
            max_retries=2,
            max_tokens=1200,  # Needs room for 3 chaos scenarios + checklist
            messages=[
                {"role": "system", "content": "You are a senior reliability engineer. Output anti-fragility and chaos hardening specs according to the Pydantic schema. Be concise but thorough."},
                {"role": "user", "content": prompt}
            ]
        )
    )
    return result

def generate_fallback_anti_fragility(
    spec: GeneratedArchitectureSpec,
    ir: IntermediateRepresentation
) -> AntiFragilityHardening:
    """
    Generates a fallback anti-fragility report if the LLM call fails or times out.
    """
    logger.warning("Generating fallback anti-fragility hardening report...")
    
    scenarios = [
        ChaosFailureScenario(
            scenario_name=f"{spec.tech_stack.database_engine} Connection Pool Exhaustion",
            failure_description=f"High concurrent write operations lock database transactions, exhausting the connection pool.",
            impact_analysis=f"HTTP 500 errors on stateful write endpoints, causing clients to drop requests or timeout.",
            mitigation_strategy="Implement connection pooling limits (e.g., PgBouncer), read replicas for SELECT operations, and client-side exponential backoff retries."
        ),
        ChaosFailureScenario(
            scenario_name="Network Blackout / API Timeout",
            failure_description="An external integration or database is temporarily unavailable during an API request.",
            impact_analysis="Endpoints depending on third-party APIs hang and time out, blocking event loop processing.",
            mitigation_strategy="Integrate the Circuit Breaker pattern with fallback responses, and queue requests asynchronously via a broker/Redis."
        ),
        ChaosFailureScenario(
            scenario_name="Uncached Query Spike",
            failure_description="Sudden traffic spike bypasses cache or hits cold cache paths, triggering slow relational database joins.",
            impact_analysis="Severe latency degradation across all list and fetch endpoints, degrading overall system response.",
            mitigation_strategy="Pre-warm cache for popular entities, use Redis with write-through pattern, and optimize index coverage on foreign keys."
        )
    ]
    
    return AntiFragilityHardening(
        resilience_rating="B",
        critical_vulnerabilities=[
            f"Lack of explicit database write-queue or rate-limiting for high-frequency telemetry",
            f"Single point of failure on the {spec.tech_stack.database_engine} instance",
            f"No circuit-breaker configuration around external API integrations"
        ],
        chaos_scenarios=scenarios,
        hardening_checklist=[
            "Configure PgBouncer or connection pool sizes matching framework worker limits.",
            "Add a Redis cache layer for high-read dashboard endpoints.",
            "Wrap external HTTP client calls in a circuit-breaker (e.g., tenacity or pybreaker).",
            "Set up structured alert thresholds for DB CPU utilization and connection counts."
        ]
    )

# -------------------------------------------------------------
# Swarm Orchestrator
# -------------------------------------------------------------

async def run_agent_swarm(
    ir: IntermediateRepresentation,
    rules: List[str],
    prompt_used: str,
    parent_spec_id: str = None,
    confidence_score: float = 1.0,
    generation_status: str = "complete"
) -> GeneratedArchitectureSpec:
    """
    Orchestrates the multi-agent design pipeline.
    
    Flow:
      1. Architect Agent (70B)        — single call, 360s timeout, RAISES on failure (no mock fallback)
      2. Concurrent gather (all 4)    — DBA + Security + PM + Anti-Fragility (8B), 60s timeout
      3. Inject metadata              — always returns a complete real spec
    
    Mock spec is ONLY used when NVIDIA_API_KEY is missing (true offline mode).
    """
    import datetime
    
    client, is_mock = get_instructor_client()
    if is_mock:
        return generate_mock_spec(ir, rules, prompt_used, parent_spec_id, confidence_score, generation_status)

    async def run_review_panel(current_spec: GeneratedArchitectureSpec):
        """Run the fast review agents plus anti-fragility for a given spec."""
        logger.info("[Swarm] Phase 2 — Dispatching DBA + Security + PM + Anti-Fragility concurrently...")
        results = await asyncio.wait_for(
            asyncio.gather(
                run_dba_agent(client, current_spec.database, rules),
                run_security_agent(client, current_spec.endpoints, rules),
                run_pm_agent(client, current_spec, prompt_used),
                run_anti_fragility_agent(client, current_spec, ir),
                return_exceptions=True
            ),
            timeout=60.0
        )
        dba_res, sec_res, pm_res, anti_frag_res = results
        logger.info("[Swarm] Phase 2 complete — all concurrent agents returned.")
        return dba_res, sec_res, pm_res, anti_frag_res
    
    # ── Phase 1: Architect Agent ─────────────────────────────────────────────
    logger.info("[Swarm] Phase 1 — Architect Agent drafting spec...")
    spec = None
    try:
        spec = await asyncio.wait_for(
            run_architect_agent(client, ir, rules, prompt_used, feedback_history=[]),
            timeout=180.0  # 3 minutes — gives 70B model full time; if it still fails, report as failed (no mock)
        )
        logger.info("[Swarm] Phase 1 complete — Architect spec received.")
    except asyncio.TimeoutError:
        # Timeout after 120s means the NVIDIA API is overloaded — report as failed, do NOT silently return mock
        logger.error("[Swarm] Architect Agent timed out after 180s. Reporting as failed.")
        raise RuntimeError("LLM generation timed out after 3 minutes. Please retry — the NVIDIA API may be under load.")
    except Exception as e:
        # Any other error (Pydantic validation, API error) — also report as failed, do NOT silently return mock
        logger.error(f"[Swarm] Architect Agent failed: {e}. Reporting as failed.")
        raise RuntimeError(f"LLM generation failed: {e}")
    
    # ── Phase 2: Concurrent Review Panel + Anti-Fragility ───────────────────
    # DBA, Security, PM → fast 8B model (compact prompts)
    # Anti-Fragility    → compact reliability prompt
    try:
        dba_res, sec_res, pm_res, anti_frag_res = await run_review_panel(spec)
    except asyncio.TimeoutError:
        logger.warning("[Swarm] Phase 2 timed out. Applying fallback anti-fragility. Spec still valid.")
        spec.anti_fragility = generate_fallback_anti_fragility(spec, ir)
        anti_frag_res = spec.anti_fragility  # prevent NameError below
        dba_res = sec_res = pm_res = Exception("timed out")
    
    # Attach anti-fragility (use fallback on failure)
    if isinstance(anti_frag_res, Exception):
        logger.warning(f"[Swarm] Anti-Fragility agent failed ({anti_frag_res}). Using fallback.")
        spec.anti_fragility = generate_fallback_anti_fragility(spec, ir)
    else:
        spec.anti_fragility = anti_frag_res
    
    # Log review results (informational — no second round-trip to save time)
    review_issues = []
    if not isinstance(dba_res, Exception) and not dba_res.passed:
        review_issues.append(f"DBA: {'; '.join(dba_res.issues)}")
    if not isinstance(sec_res, Exception) and not sec_res.passed:
        review_issues.append(f"Security: {'; '.join(sec_res.issues)}")
    if not isinstance(pm_res, Exception) and not pm_res.passed:
        review_issues.append(f"PM: {'; '.join(pm_res.issues)}")
    
    if review_issues:
        logger.info(f"[Swarm] Review panel flagged issues (logged, no revision cycle): {review_issues}")
    else:
        logger.info("[Swarm] Review panel: all agents passed.")
 
    if review_issues:
        logger.info("[Swarm] Review panel requested a revision pass; rerunning architect once with feedback.")
        spec = await asyncio.wait_for(
            run_architect_agent(client, ir, rules, prompt_used, feedback_history=review_issues),
            timeout=120.0
        )
        try:
            dba_res, sec_res, pm_res, anti_frag_res = await run_review_panel(spec)
        except asyncio.TimeoutError:
            logger.warning("[Swarm] Revision review panel timed out. Applying fallback anti-fragility.")
            spec.anti_fragility = generate_fallback_anti_fragility(spec, ir)
            anti_frag_res = spec.anti_fragility
            dba_res = sec_res = pm_res = Exception("timed out")
 
        if isinstance(anti_frag_res, Exception):
            logger.warning(f"[Swarm] Revision anti-fragility agent failed ({anti_frag_res}). Using fallback.")
            spec.anti_fragility = generate_fallback_anti_fragility(spec, ir)
        else:
            spec.anti_fragility = anti_frag_res

        review_issues = []
        if not isinstance(dba_res, Exception) and not dba_res.passed:
            review_issues.append(f"DBA: {'; '.join(dba_res.issues)}")
        if not isinstance(sec_res, Exception) and not sec_res.passed:
            review_issues.append(f"Security: {'; '.join(sec_res.issues)}")
        if not isinstance(pm_res, Exception) and not pm_res.passed:
            review_issues.append(f"PM: {'; '.join(pm_res.issues)}")

        if review_issues:
            logger.info(f"[Swarm] Revision review panel still flagged issues: {review_issues}")
        else:
            logger.info("[Swarm] Revision review panel passed.")
    
    # ── Phase 3: Inject Final Metadata ──────────────────────────────────────
    spec.metadata = SpecMetadata(
        version="1.0.0" if not parent_spec_id else "1.1.0",
        parent_spec_id=parent_spec_id,
        created_at=datetime.datetime.utcnow().isoformat(),
        prompt_used=prompt_used,
        confidence_score=confidence_score,
        generation_status="complete"
    )
    logger.info("[Swarm] Pipeline complete. Returning final spec.")
    return spec

# -------------------------------------------------------------
# Mock Fallback Generator (For testing/offline)
# -------------------------------------------------------------

def generate_mock_spec(
    ir: IntermediateRepresentation,
    rules: List[str],
    prompt_used: str,
    parent_spec_id: str = None,
    confidence_score: float = 1.0,
    generation_status: str = "complete"
) -> GeneratedArchitectureSpec:
    """
    Generates a high-quality mock architectural specification matching the target archetype.
    Used for local offline testing when NVIDIA_API_KEY is not configured.
    """
    import datetime
    logger.info("Generating mock architecture spec...")
    
    # Baseline defaults
    lang = "Python"
    framework = "FastAPI"
    db = "PostgreSQL"
    cache = "Redis"
    auth = "JWT"
    
    # Customize based on archetype
    arch_lower = ir.archetype.lower()
    if "e-commerce" in arch_lower:
        lang, framework = "TypeScript", "Next.js"
    elif "collaborative" in arch_lower:
        lang, framework, db = "TypeScript", "NestJS", "MongoDB"
    elif "iot" in arch_lower:
        lang, framework, db = "Go", "Gin", "TimescaleDB"
        
    tables = [
        TableSchema(
            name="users",
            description="User authentication and profile storage",
            columns=[
                ColumnSchema(name="id", type="UUID", is_primary_key=True),
                ColumnSchema(name="email", type="String", is_nullable=False),
                ColumnSchema(name="password_hash", type="String", is_nullable=False),
                ColumnSchema(name="created_at", type="DateTime", is_nullable=False)
            ]
        )
    ]
    
    # Add entities dynamically
    for entity in ir.entities:
        ent_name = entity.lower().replace(" ", "_")
        if ent_name not in ("user", "users"):
            tables.append(
                TableSchema(
                    name=ent_name if ent_name.endswith("s") else f"{ent_name}s",
                    description=f"Storage for {entity} records",
                    columns=[
                        ColumnSchema(name="id", type="UUID", is_primary_key=True),
                        ColumnSchema(name="user_id", type="UUID", foreign_key="users.id"),
                        ColumnSchema(name="created_at", type="DateTime", is_nullable=False)
                    ]
                )
            )
            
    endpoints = [
        EndpointSchema(
            method="POST",
            path="/api/v1/auth/register",
            summary="Registers a new user",
            is_protected=False,
            response_payload_schema="status: success, user_id: string"
        ),
        EndpointSchema(
            method="POST",
            path="/api/v1/auth/login",
            summary="Authenticates user and returns JWT",
            is_protected=False,
            response_payload_schema="access_token: string, token_type: bearer"
        )
    ]
    
    for table in tables:
        if table.name != "users":
            endpoints.append(
                EndpointSchema(
                    method="GET",
                    path=f"/api/v1/{table.name}",
                    summary=f"Retrieves all {table.name}",
                    is_protected=True,
                    response_payload_schema="items: array"
                )
            )
            endpoints.append(
                EndpointSchema(
                    method="POST",
                    path=f"/api/v1/{table.name}",
                    summary=f"Creates a new {table.name[:-1]}",
                    is_protected=True,
                    request_payload_schema="data: object",
                    response_payload_schema="id: string, status: created"
                )
            )
            
    business_rules = [
        BusinessRule(
            rule=rule.split(":")[1].strip() if ":" in rule else rule,
            reason=f"Derived from architectural constraint for {ir.archetype}"
        ) for rule in rules[:3]
    ]
    
    spec = GeneratedArchitectureSpec(
        metadata=SpecMetadata(
            version="1.0.0" if not parent_spec_id else "1.1.0",
            parent_spec_id=parent_spec_id,
            created_at=datetime.datetime.utcnow().isoformat(),
            prompt_used=prompt_used,
            confidence_score=confidence_score,
            generation_status=generation_status
        ),
        project_name=f"{ir.entities[0] if ir.entities else 'Baxel'}App",
        tech_stack=TechStack(
            language=lang,
            framework=framework,
            database_engine=db,
            cache=cache
        ),
        auth_strategy=AuthStrategy(
            method=auth,
            token_expiry_seconds=3600,
            refresh_token_supported=True
        ),
        database=DatabaseSchema(tables=tables),
        endpoints=endpoints,
        business_rules=business_rules,
        devops=DevOpsSetup(
            environment_variables=["DATABASE_URL", "JWT_SECRET", "REDIS_URL"],
            dockerfile_content=f"FROM python:3.11\nWORKDIR /app\nCOPY . .\nRUN pip install -r requirements.txt\nCMD [\"uvicorn\", \"main:app\", \"--host\", \"0.0.0.0\"]",
            docker_compose_content=f"version: '3.8'\nservices:\n  web:\n    build: .\n    ports:\n      - \"8000:8000\"\n  redis:\n    image: redis:alpine"
        ),
        spice=SpiceLayer(
            devils_advocate="Ensure database indexing is configured properly for composite primary keys under high tenant concurrency load.",
            design_rationale=f"Selected {framework} and {db} to optimize real-time speed and relational safety required by the {ir.archetype} archetype.",
            estimated_time_saved_hours=12
        )
    )
    spec.anti_fragility = generate_fallback_anti_fragility(spec, ir)
    return spec
