import os
import logging
import asyncio
from typing import List, Dict, Any, Tuple
from openai import OpenAI
import instructor
from dotenv import load_dotenv

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
load_dotenv()

logger = logging.getLogger(__name__)

# LLM Configurations
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://integrate.api.nvidia.com/v1")
LLM_MODEL = os.getenv("LLM_MODEL", "meta/llama-3.3-70b-instruct")
# Lightweight model for fast review agents (DBA, Security, PM) — much lower latency
LLM_REVIEW_MODEL = os.getenv("LLM_REVIEW_MODEL", "meta/llama-3.1-8b-instruct")

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
    
    IMPORTANT: timeout=150 is set at the HTTP level so the underlying socket
    closes after 150s even if asyncio.wait_for cancels the coroutine.
    Without this, the executor thread keeps blocking indefinitely (OpenAI default = 600s).
    """
    api_key = _load_api_key()
    if not api_key:
        logger.warning("NVIDIA_API_KEY not found. Falling back to local Mock Generator.")
        return None, True
    try:
        client = OpenAI(
            api_key=api_key,
            base_url=LLM_BASE_URL,
            timeout=150.0  # Hard HTTP-level timeout — prevents executor thread from blocking forever
        )
        instructor_client = instructor.from_openai(client)
        return instructor_client, False
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}. Falling back to mock.")
        return None, True

# -------------------------------------------------------------
# Agent Definitions
# -------------------------------------------------------------

async def run_architect_agent(
    client: Any,
    ir: IntermediateRepresentation,
    rules: List[str],
    prompt_used: str,
    feedback_history: List[str] = None
) -> GeneratedArchitectureSpec:
    """
    Principal Architect Agent: Drafts or refines the system design specification.
    """
    logger.info("Principal Architect drafting system design...")
    
    # Truncate input spec to prevent NVIDIA API timeout on large specs (>5000 chars).
    # The NLP-extracted IR (entities, actors, integrations) already captures the full context,
    # so truncating the raw text is safe and cuts architect processing time by ~50%.
    MAX_SPEC_CHARS = 4500
    spec_excerpt = prompt_used[:MAX_SPEC_CHARS]
    if len(prompt_used) > MAX_SPEC_CHARS:
        spec_excerpt += f"\n[...{len(prompt_used) - MAX_SPEC_CHARS} chars truncated — full context captured in entities below...]"
        logger.info(f"Spec truncated from {len(prompt_used)} to {MAX_SPEC_CHARS} chars for architect prompt.")
    
    # Build dynamic component list from NLP-extracted entities
    entity_list = "\n".join([f"   - {e}" for e in ir.entities]) if ir.entities else "   - (see spec excerpt above)"
    
    prompt = f"""
    You are a Principal Software Architect. Draft a detailed system design specification.
    
    User Spec Excerpt (primary source — read carefully):
    {spec_excerpt}
    
    NLP-Extracted Context (supplementary — covers the full spec):
    - System Archetype: {ir.archetype}
    - All Domain Entities (MUST each have dedicated DB tables and endpoints):
{entity_list}
    - User Roles/Actors: {', '.join(ir.actors)}
    - Required Integrations: {', '.join(ir.implied_integrations)}
    
    Architectural Rules:
    {chr(10).join([f'- {r}' for r in rules])}
    
    STRICT REQUIREMENTS:
    1. Generate MINIMUM 8 separate database tables — one per major domain entity above. Do NOT group entities.
    2. Generate MINIMUM 15 API endpoints covering the full lifecycle of every entity.
    3. Every table must have 4+ columns (id, foreign keys, domain-specific fields, timestamps).
    4. Tech stack, auth strategy, business rules, and devops must be production-grade and domain-specific.
    5. Never produce generic/placeholder output — all names, fields, and endpoints must reflect this specific system.
    """
    
    if feedback_history:
        prompt += f"\n\nCRITICAL FIXES REQUIRED FROM PREVIOUS REVIEW:\n" + "\n".join(feedback_history)
        prompt += "\nModify the previous design to fix all issues listed above."
        
    loop = asyncio.get_running_loop()
    
    # Run in executor to prevent blocking the event loop
    # max_tokens=6000 caps output length — prevents runaway generation on large specs
    spec = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=GeneratedArchitectureSpec,
            max_retries=2,  # Reduced from 3 to save time on validation loops
            max_tokens=8000,  # Increased: large input specs need more output budget for rich schemas
            messages=[
                {"role": "system", "content": "You are an expert principal software architect. Generate a HIGHLY DETAILED architecture spec matching the Pydantic schema. MINIMUM 8 database tables, MINIMUM 12 API endpoints. Every domain in the user's spec MUST have its own dedicated tables and endpoints. Never collapse multiple domains into a single table. Never produce placeholder or minimal output."},
                {"role": "user", "content": prompt}
            ]
        )
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
- Stack: {spec.tech_stack.language}/{spec.tech_stack.framework}, DB={spec.tech_stack.database_engine}, Cache={spec.tech_stack.cache}
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
    
    Flow (optimized for speed):
      1. Architect Agent (70B)        — single draft, 180s timeout
      2. Concurrent gather (all 4)    — DBA + Security + PM (8B) + Anti-Fragility (70B), 60s timeout
      3. Inject metadata              — always returns a complete spec
    """
    import datetime
    
    client, is_mock = get_instructor_client()
    if is_mock:
        return generate_mock_spec(ir, rules, prompt_used, parent_spec_id, confidence_score, generation_status)
    
    # ── Phase 1: Architect Agent ─────────────────────────────────────────────
    logger.info("[Swarm] Phase 1 — Architect Agent drafting spec...")
    spec = None
    try:
        spec = await asyncio.wait_for(
            run_architect_agent(client, ir, rules, prompt_used, feedback_history=[]),
            timeout=180.0
        )
        logger.info("[Swarm] Phase 1 complete — Architect spec received.")
    except Exception as e:
        logger.error(f"[Swarm] Architect Agent failed: {e}. Falling back to mock spec.")
        return generate_mock_spec(ir, rules, prompt_used, parent_spec_id, confidence_score, generation_status)
    
    # ── Phase 2: Concurrent Review Panel + Anti-Fragility ───────────────────
    # DBA, Security, PM → fast 8B model (compact prompts)
    # Anti-Fragility    → 70B model (needs structured chaos scenario output)
    # All 4 run simultaneously in a thread pool — total wait = slowest task
    logger.info("[Swarm] Phase 2 — Dispatching DBA + Security + PM + Anti-Fragility concurrently...")
    try:
        results = await asyncio.wait_for(
            asyncio.gather(
                run_dba_agent(client, spec.database, rules),
                run_security_agent(client, spec.endpoints, rules),
                run_pm_agent(client, spec, prompt_used),
                run_anti_fragility_agent(client, spec, ir),
                return_exceptions=True
            ),
            timeout=60.0  # All 4 agents now use the fast 8B model — should complete well within 60s
        )
        dba_res, sec_res, pm_res, anti_frag_res = results
        logger.info("[Swarm] Phase 2 complete — all concurrent agents returned.")
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
