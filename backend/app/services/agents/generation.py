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


class _ProjectMetaSpec(BaseModel):
    project_name: str
    tech_stack: TechStack
    auth_strategy: AuthStrategy


class _DatabaseTablesChunk(BaseModel):
    tables: List[TableSchema]


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
# Review agents (DBA, Security, PM, Anti-Fragility), entity extraction, and the SAGE
# intent classifier all use this model.
# NOTE: meta/llama-3.1-8b-instruct (the previous value here) was deprecated by NVIDIA NIM
# on 2026-08-26 and now returns HTTP 410 Gone — it is no longer callable at all. Moved to
# openai/gpt-oss-20b (same model as the Architect/SAGE). That model emits hidden
# chain-of-thought reasoning before its JSON answer, so every call site using this
# constant has its max_tokens sized generously above the old 8B-tuned values to leave
# room for that reasoning — a tight budget here means IncompleteOutputException, not a
# slow response.
LLM_REVIEW_MODEL = "openai/gpt-oss-20b"
# SAGE Chatbot model configuration
LLM_SAGE_MODEL = "openai/gpt-oss-20b"

# -------------------------------------------------------------
# System Prompts (Agent Swarm)
# -------------------------------------------------------------
# Persona + standing constraints live in the system message, not the user
# message — the model weighs system instructions more heavily and it keeps
# these rules from getting lost among the per-call spec context below.

SYSTEM_PROMPT_DB_ARCHITECT = """You are a Principal Software Architect specializing in relational database design for production SaaS systems.

Output rules:
- Output ONLY compact JSON matching the requested schema — no markdown, no commentary, no filler text outside the JSON.
- Every table must have a primary key. Enforce foreign keys wherever one table clearly references another.
- Use Enum (with explicit enum_values) for any stateful column such as status, verification, or payment/booking state.
- You MUST fully write out every table and every column as real JSON objects. NEVER insert a placeholder, summary, or truncation marker (e.g. "...", "// remaining tables omitted", "{...JSON truncated...}") anywhere in the array in place of actual content — that produces invalid JSON and the whole response is discarded. If the schema is large, keep table/column descriptions terse to save space, but every table must still be a complete, real object with all its columns spelled out. An incomplete but valid-looking response is worse than useless — it fails outright.

Grounding rules:
- Model every domain concept the user's spec actually describes, including payment models, workflows, and custom entity relationships — even if they appear late in the spec, not just the opening sentences.
- Do NOT invent generic marketplace constructs (commissions, escrow, independent reviews, etc.) unless the user's spec explicitly asks for them. A plausible-sounding addition is still wrong if it isn't grounded in what the user wrote."""

SYSTEM_PROMPT_API_ARCHITECT = """You are a Principal Software Architect specializing in RESTful API design.

Output rules:
- Output ONLY compact JSON matching the requested schema — no markdown, no commentary.
- You MUST only reference tables that exist in the database context you are given. Never invent endpoints for a subsystem that has no backing table.

Design rules:
- Define a complete REST contract for the given tables and auth strategy; mark every endpoint as protected or not.
- For any table with a status/state column, add dedicated transition endpoints (e.g. PATCH /bookings/{id}/status) rather than only exposing status as an editable PUT field.
- Include the specific action endpoints implied by the business requirements (verification pipelines, payout execution, refund processing, dispute creation, etc.).
- Populate error_responses with realistic 3-digit HTTP status codes (e.g. ['400', '401', '403', '404', '409']) — never leave it empty."""

SYSTEM_PROMPT_BUSINESS_RULES = """You are a Principal Software Architect writing enforceable business rules for a generated backend.

Output rules:
- Output ONLY compact JSON matching the requested schema — no markdown, no commentary.
- You MUST only reference tables and concepts present in the database context you are given. Never invent a rule for a subsystem that has no backing table.
- Every rule must be a specific, checkable constraint or state-transition guard derived from the user's prompt — not a generic platitude like "validate user input.\""""

SYSTEM_PROMPT_DEVOPS = """You are a DevOps and Cloud Infrastructure Engineer producing deployment config for a freshly generated backend.

Output rules:
- Output ONLY compact JSON matching the requested schema — no markdown, no commentary.
- The Dockerfile must be production-ready for the exact tech stack given (correct base image, dependency install step, correct start command) — not a generic placeholder.
- List only the environment variable keys this specific stack actually needs.
- If you include docker-compose.yml, wire the database, a Redis cache, and the backend service together with real service names and correct port mappings."""

SYSTEM_PROMPT_SPICE = """You are a Principal Software Architect and Tech Lead giving a candid technical opinion on an already-generated design.

Output rules:
- Output ONLY compact JSON matching the requested schema — no markdown, no commentary.
- devils_advocate must name a real failure point or trade-off this specific stack has at scale — not a generic "watch your database performance" warning.
- design_rationale must explain why this stack fits this archetype specifically, referencing the actual project and stack given.
- estimated_time_saved_hours should be a plausible, defensible estimate, not a round default."""

SYSTEM_PROMPT_RESILIENCE = """You are a Chaos Engineering and Reliability Architect stress-testing a freshly generated system design.

Output rules:
- Output ONLY compact JSON matching the requested schema — no markdown, no commentary.
- Every failure scenario, vulnerability, and checklist item MUST be grounded in this system's actual tables, endpoints, and stack. Never reuse the illustrative examples from the schema's field descriptions (e.g. "Acoustic Telemetry", "Ledger DB Lock") — those are placeholders, not real scenarios for this project.
- Prefer concrete, plausible failure modes: database locks, payment/webhook failures, API load spikes, websocket drops, cache stampedes — whichever actually apply to this project's domain."""

SYSTEM_PROMPT_DBA_REVIEWER = """You are a senior Database Administrator doing a fast pre-launch schema review.

Set passed=false ONLY for genuine correctness defects:
- A table with no primary key.
- A column that clearly references another entity (e.g. *_id) but has no foreign key set.
- An obvious tenant-isolation gap — user- or org-scoped data with no user_id/tenant_id column at all.

Do NOT fail the schema for missing indexes, naming style, or normalization preferences — those are advisory, not blocking. Every issue you list must name the specific table and column it applies to; no vague feedback."""

SYSTEM_PROMPT_SECURITY_REVIEWER = """You are a senior Application Security engineer auditing an API surface before launch.

Set passed=false ONLY if a write/delete endpoint (POST/PUT/PATCH/DELETE) is unprotected without an obvious reason (e.g. a public signup/login route is expected to be unprotected — that is not a finding). A protected read-only GET on public data is also not a finding.

Do NOT flag rate-limiting, CORS, or other infra-level concerns — those are out of scope for this review. Every issue you list must cite the exact "METHOD /path" it applies to."""

SYSTEM_PROMPT_PM_REVIEWER = """You are a Product Manager verifying a generated backend spec actually covers what the user asked for.

Set passed=false ONLY if a requirement explicitly stated in the user's original prompt has no corresponding table, field, or endpoint anywhere in the generated spec. Do NOT fail the spec for missing nice-to-haves the user never mentioned — you are checking coverage of stated requirements, not proposing new scope."""

SYSTEM_PROMPT_ANTI_FRAGILITY = """You are a senior Site Reliability Engineer running a chaos-engineering pass on a freshly generated architecture.

- Assign resilience_rating based on genuine risk in this specific system — do not default to a fixed grade.
- Every scenario and vulnerability must name the exact component (table, endpoint, or stack piece) that fails; generic scenarios are not acceptable.
- Be concise but concrete — prefer one precisely-described failure mode over three vague ones."""

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
    gives the Architect model enough time to generate a full spec.
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
            timeout=360.0  # 6-minute socket timeout — gives the Architect model full time to respond
        )
        instructor_client = instructor.from_openai(client, mode=instructor.Mode.JSON)
        return instructor_client, False
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}. Falling back to mock.")
        return None, True

# -------------------------------------------------------------
# Agent Definitions
# -------------------------------------------------------------

# Small/typical specs stay on the single-call path below — that path is what every
# tier was tested and confirmed working against, so it stays byte-for-byte unchanged
# to carry zero regression risk for the common case. For large/complex specs, Phase
# 1A's single monolithic schema call was observed live taking 250-900s+ on a 15-18
# table Enterprise-tier spec, because the reasoning model's hidden chain-of-thought
# cost grows with how many entities/tables it has to reason through in one response.
# Splitting entities into smaller concurrent chunks (mirroring the pattern Phase 1B
# already uses for endpoints/business_rules/devops/spice/resilience) means each call
# reasons over far fewer entities and finishes in the same 40-90s range small specs
# already do — wall-clock time becomes ~the slowest chunk, not the sum of all of them,
# with no reduction in the number of tables/columns actually produced. See
# _generate_database_spec below for the chunking trigger condition.
# Was 6 — smaller chunks give the model less to track per call, which should make full
# coverage of the assigned entities easier to reliably hit (see the completeness-check
# comment in _generate_database_spec_chunked for why coverage sometimes fell short at
# size 6).
DATABASE_CHUNK_SIZE = 4


async def _generate_project_meta(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    feedback_history: List[str] = None
) -> _ProjectMetaSpec:
    """Cheap, fast call for project_name/tech_stack/auth_strategy — runs concurrently
    alongside the table chunks below since it doesn't depend on the schema itself."""
    entity_list = ", ".join(ir.entities[:20]) if ir.entities else "none"
    actor_list = ", ".join(ir.actors[:10]) if ir.actors else "none"

    prompt = f"""
    User Spec Excerpt:
    {spec_excerpt}

    NLP Context:
    - Archetype: {ir.archetype}
    - Entities: {entity_list}
    - Actors: {actor_list}

    Task: Choose project_name, tech_stack, and auth_strategy for this system. Do NOT
    design the database schema — that is handled by separate parallel calls.
    """
    if feedback_history:
        prompt += "\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_ProjectMetaSpec,
            max_retries=2,
            max_tokens=1024,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_DB_ARCHITECT},
                {"role": "user", "content": prompt}
            ]
        )
    )


async def _generate_database_chunk(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    rules: List[str],
    entity_subset: List[str],
    chunk_index: int,
    total_chunks: int,
    feedback_history: List[str] = None
) -> _DatabaseTablesChunk:
    """Generates tables for ONE subset of entities. Given the FULL entity list as
    foreign-key context so it can reference tables owned by other concurrent chunks by
    name, without redefining them itself."""
    all_entities = ", ".join(ir.entities) if ir.entities else "none"
    assigned_list = list(entity_subset)
    assigned = ", ".join(assigned_list)
    assigned_checklist = "\n".join([f"  {i+1}. {e}" for i, e in enumerate(assigned_list)])
    actor_list = ", ".join(ir.actors[:10]) if ir.actors else "none"
    integration_list = ", ".join(ir.implied_integrations[:10]) if ir.implied_integrations else "none"

    prompt = f"""
    User Spec Excerpt:
    {spec_excerpt}

    NLP Context:
    - Archetype: {ir.archetype}
    - ALL entities in the full system (context only — other entities are being designed
      by parallel calls; reference them by table name via foreign_key when a
      relationship crosses into one, but do NOT define tables for them yourself):
      {all_entities}
    - Actors: {actor_list}
    - Integrations: {integration_list}

    Rules:
    {chr(10).join([f'- {r}' for r in rules])}

    Task: Design database tables for EXACTLY these {len(assigned_list)} assigned entities
    — no more, no fewer:
    {assigned_checklist}

    Before answering, verify your `tables` array has at least {len(assigned_list)} entries,
    one per assigned entity above (you may add a small extra junction/support table if a
    relationship genuinely needs one, but every listed entity must have its own table —
    do not skip, merge, or omit any of them).
    (This is chunk {chunk_index + 1} of {total_chunks}.)
    """
    if feedback_history:
        prompt += "\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_DatabaseTablesChunk,
            max_retries=3,
            max_tokens=8192,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_DB_ARCHITECT},
                {"role": "user", "content": prompt}
            ]
        )
    )


async def _try_database_spec_chunked_once(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    rules: List[str],
    feedback_history: List[str] = None
):
    """
    One independent attempt at chunked generation. Returns a complete _DatabaseSpec, or
    None if this attempt was incomplete/failed (an exception in any chunk, or fewer
    tables than named entities — see _generate_database_spec_chunked for why both are
    treated as failures). Returning None (rather than falling back internally) lets the
    caller retry with a second independent attempt before paying for the much slower
    single-call path.
    """
    entities = ir.entities
    chunks = [entities[i:i + DATABASE_CHUNK_SIZE] for i in range(0, len(entities), DATABASE_CHUNK_SIZE)]
    logger.info(
        f"[Swarm] Large spec ({len(entities)} entities) — attempting Phase 1A as "
        f"{len(chunks)} concurrent chunk calls instead of one monolithic call."
    )

    meta_task = _generate_project_meta(client, loop, spec_excerpt, ir, feedback_history)
    chunk_tasks = [
        _generate_database_chunk(client, loop, spec_excerpt, ir, rules, chunk, idx, len(chunks), feedback_history)
        for idx, chunk in enumerate(chunks)
    ]

    results = await asyncio.gather(meta_task, *chunk_tasks, return_exceptions=True)
    meta_result, chunk_results = results[0], results[1:]

    if isinstance(meta_result, Exception):
        logger.warning(f"[Swarm] Chunked project-meta call failed ({meta_result}).")
        return None

    # ANY chunk failure — not just all of them — fails this attempt. Observed live: one
    # chunk hit the model's known "lazy truncation placeholder" bug (emitting a literal
    # "{...}" instead of a full table object) even after its own 3 retries, and skipping
    # just that chunk's entities once silently shipped a schema missing the Project and
    # Task tables — the two most important tables in a project-management app — while
    # the pipeline still reported success. A partial schema is a correctness failure
    # regardless of how many other chunks succeeded.
    all_tables: List[TableSchema] = []
    seen_names = set()
    for chunk_result in chunk_results:
        if isinstance(chunk_result, Exception):
            logger.warning(f"[Swarm] A database chunk call failed ({chunk_result}).")
            return None
        for table in chunk_result.tables:
            if table.name in seen_names:
                logger.warning(f"[Swarm] Duplicate table '{table.name}' returned by multiple chunks; keeping the first.")
                continue
            seen_names.add(table.name)
            all_tables.append(table)

    # A second, more insidious failure mode than an outright exception: a chunk call can
    # return a 200-OK, schema-valid response that still only covers SOME of its assigned
    # entities — no exception is raised, so the check above never catches it. Observed
    # live: 2 chunks covering 12 named entities (6 each) returned only 7 tables total,
    # silently dropping Task, Workspace, Team, Comment, Subtask, and Notification, while
    # both chunk calls "succeeded." A real schema for N named entities always has AT
    # LEAST N tables in practice (schemas add junction/support tables, they don't merge
    # named entities together), so fewer tables than entities is a reliable signal of
    # silent incompleteness.
    if not all_tables or len(all_tables) < len(entities):
        logger.warning(
            f"[Swarm] Chunked generation produced only {len(all_tables)} tables for "
            f"{len(entities)} named entities — looks incomplete."
        )
        return None

    return _DatabaseSpec(
        project_name=meta_result.project_name,
        tech_stack=meta_result.tech_stack,
        auth_strategy=meta_result.auth_strategy,
        database=DatabaseSchema(tables=all_tables)
    )


async def _generate_database_spec_chunked(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    rules: List[str],
    feedback_history: List[str] = None
) -> _DatabaseSpec:
    # One retry of the (fast) chunked path before falling back to the (slow) single-call
    # path. Observed live: a failed/incomplete chunked attempt used to fall straight back
    # to a full single-call regeneration, effectively paying for Phase 1A TWICE — once
    # for the chunked attempt (~200s) and again for the single-call fallback (~200s+),
    # stretching one generation to 12+ minutes. A second independent chunked attempt is
    # still much faster than the single-call path when it succeeds, and chunking has
    # succeeded more often than not across live testing — so it's worth one more fast
    # try before paying the expensive, guaranteed-complete fallback.
    result = await _try_database_spec_chunked_once(client, loop, spec_excerpt, ir, rules, feedback_history)
    if result is not None:
        return result

    logger.warning("[Swarm] First chunked attempt was incomplete — retrying chunked generation once more before falling back.")
    result = await _try_database_spec_chunked_once(client, loop, spec_excerpt, ir, rules, feedback_history)
    if result is not None:
        return result

    logger.warning("[Swarm] Second chunked attempt also incomplete — falling back to single-call generation.")
    return await _generate_database_spec_single(client, loop, spec_excerpt, ir, rules, feedback_history)


async def _generate_database_spec_single(
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
    """
    if feedback_history:
        prompt += f"\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_DatabaseSpec,
            # This is the one call the whole run has no fallback for (run_agent_swarm
            # raises straight to a 500 if it fails). Observed live: the model can emit
            # a lazy truncation placeholder instead of the full JSON on a large schema,
            # and back-to-back retries can both fail this way — 3 attempts (paired with
            # the anti-truncation instruction above) gives real recovery odds instead of
            # just halving the failure rate once.
            max_retries=3,
            max_tokens=16384,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_DB_ARCHITECT},
                {"role": "user", "content": prompt}
            ]
        )
    )


def _should_chunk_database_spec(entities: List[str], spec_excerpt: str) -> bool:
    """
    Shared decision used both to pick Phase 1A's generation path AND (in
    run_architect_agent) to decide whether DevOps/Spice can safely start early
    alongside Phase 1A — see the "early DevOps/Spice" comment there for why.

    Chunking needs BOTH a size signal (the actual driver of Phase 1A latency) AND
    enough named entities to split into more than one useful chunk. Keying this off
    entity count alone is unreliable — the NLP entity-extraction step has its own
    fallback chain (LLM extraction -> GLiNER -> regex) and can under-extract on a
    long, dense spec, leaving too few named entities to trigger chunking even though
    the spec itself is exactly the large/complex case chunking exists for.
    """
    size_signal = max(len(spec_excerpt), len(entities) * 400)
    return size_signal > 2200 and len(entities) >= 4


async def _generate_database_spec(
    client: Any,
    loop: Any,
    spec_excerpt: str,
    ir: IntermediateRepresentation,
    rules: List[str],
    feedback_history: List[str] = None
) -> _DatabaseSpec:
    entities = ir.entities or []
    if not _should_chunk_database_spec(entities, spec_excerpt):
        return await _generate_database_spec_single(client, loop, spec_excerpt, ir, rules, feedback_history)
    return await _generate_database_spec_chunked(client, loop, spec_excerpt, ir, rules, feedback_history)


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
    User Spec Excerpt:
    {spec_excerpt}

    Database context (existing tables):
    {table_names}

    Task: Generate only API endpoints matching the database tables above.
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
                {"role": "system", "content": SYSTEM_PROMPT_API_ARCHITECT},
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
    User Spec Excerpt:
    {spec_excerpt}

    Database tables:
    {table_names}

    Task: Generate only the business_rules list, derived from the user prompt and rules above.
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
                {"role": "system", "content": SYSTEM_PROMPT_BUSINESS_RULES},
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
    Tech Stack:
    {tech_stack_desc}

    Task: Generate the devops setup details for this stack.
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
                {"role": "system", "content": SYSTEM_PROMPT_DEVOPS},
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
    Project Name: {db_spec.project_name}
    Tech Stack: {db_spec.tech_stack.language} / {db_spec.tech_stack.framework} / {db_spec.tech_stack.database_engine}

    Task: Generate the spice layer (devils_advocate, design_rationale, estimated_time_saved_hours) for this project.
    """
    if feedback_history:
        prompt += f"\n\nRevision notes:\n" + "\n".join(feedback_history)

    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_MODEL,
            response_model=_SpiceSpec,
            max_retries=0,
            # Was 16384 — wildly oversized for a 3-field output (devils_advocate,
            # design_rationale, estimated_time_saved_hours). A live run showed this call
            # alone stretching Phase 1B to ~4 minutes before failing validation and
            # falling back; the oversized budget was letting the reasoning model "think"
            # far longer than this tiny output needs. Verified live: 4096 succeeds just
            # as reliably and is 2.5x faster (23.9s -> 9.5s on the same prompt).
            max_tokens=4096,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_SPICE},
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
    Project: {db_spec.project_name}
    Archetype: {ir.archetype}
    Tables: {table_names}

    Task: Generate the anti_fragility plan for this project.
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
            # Was 16384 — output here is bounded (a rating, a short vulnerability list,
            # exactly 3 chaos scenarios, a 4-step checklist), so the same oversized-budget
            # problem as Spice applied. Verified live: 4096 succeeds just as reliably and
            # is 2x faster (45.1s -> 22.1s on the same prompt).
            max_tokens=4096,
            temperature=1.00,
            top_p=1.00,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_RESILIENCE},
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


def _truncate_spec_excerpt(prompt_used: str) -> str:
    """Keep the architect prompt compact — shared by the initial pass and any revision."""
    MAX_SPEC_CHARS = 9000
    spec_excerpt = prompt_used[:MAX_SPEC_CHARS]
    if len(prompt_used) > MAX_SPEC_CHARS:
        spec_excerpt += f"\n[...{len(prompt_used) - MAX_SPEC_CHARS} chars truncated...]"
        logger.info(f"Spec truncated from {len(prompt_used)} to {MAX_SPEC_CHARS} chars for architect prompt.")
    return spec_excerpt


async def run_targeted_revision(
    client: Any,
    ir: IntermediateRepresentation,
    rules: List[str],
    prompt_used: str,
    spec: GeneratedArchitectureSpec,
    endpoints_feedback: List[str] = None,
    business_rules_feedback: List[str] = None,
) -> GeneratedArchitectureSpec:
    """
    Cheaper alternative to a full run_architect_agent revision pass, used when the DBA
    agent passed (schema itself is sound) but Security and/or PM flagged issues that
    only implicate endpoints and/or business rules. Regenerates just those pieces
    against the EXISTING database schema and splices the results back into `spec` —
    skips redoing the DB spec call and the 3 untouched Phase 1B calls (devops, spice,
    resilience) entirely, since none of those depend on what Security/PM flagged.
    """
    spec_excerpt = _truncate_spec_excerpt(prompt_used)
    loop = asyncio.get_running_loop()

    tasks = {}
    if endpoints_feedback:
        tasks["endpoints"] = _generate_endpoints_spec(client, loop, spec_excerpt, ir, spec, rules, endpoints_feedback)
    if business_rules_feedback:
        tasks["business_rules"] = _generate_business_rules_spec(client, loop, spec_excerpt, ir, spec, rules, business_rules_feedback)

    if not tasks:
        return spec

    results = await asyncio.gather(*tasks.values(), return_exceptions=True)
    results_by_key = dict(zip(tasks.keys(), results))

    if "endpoints" in results_by_key:
        ep_result = results_by_key["endpoints"]
        if isinstance(ep_result, Exception):
            logger.warning(f"[Swarm] Targeted endpoints revision failed ({ep_result}). Keeping prior endpoints.")
        else:
            spec.endpoints = ep_result.endpoints

    if "business_rules" in results_by_key:
        br_result = results_by_key["business_rules"]
        if isinstance(br_result, Exception):
            logger.warning(f"[Swarm] Targeted business rules revision failed ({br_result}). Keeping prior business rules.")
        else:
            spec.business_rules = br_result.business_rules

    return _normalize_generated_spec(spec)


def _compute_phase_timeouts(ir: IntermediateRepresentation, prompt_used: str) -> tuple:
    """
    Scales Phase 1A/1B timeout budgets to spec size instead of using one flat number
    for every request. A flat 450s budget still timed out live on a large 9-module
    Enterprise-tier spec (WorkForge, ~6500 chars) across four consecutive real runs
    (251s/288s/>360s/>450s), while small specs (~1100-1700 chars) reliably finish
    Phase 1A in well under 100s. The reasoning model's hidden chain-of-thought cost
    grows with how many entities/tables it has to reason through and emit, so the
    budget should grow with the spec's size rather than chase one fixed ceiling.

    `size_signal` uses whichever proxy is larger: prompt character count (always
    available) or entity count from the NLP-extracted IR (catches short-but-dense
    prompts that still imply a large number of entities).
    """
    chars = len(prompt_used or "")
    entity_count = len(ir.entities) if ir and getattr(ir, "entities", None) else 0
    size_signal = max(chars, entity_count * 400)

    # Cap raised 900s -> 1200s: on a large spec, Phase 1A can now internally spend a
    # chunked attempt, a chunked retry, AND a single-call fallback in the worst case
    # (see _generate_database_spec_chunked) — needs enough combined room for all three
    # rather than just one single-call-sized budget.
    phase_1a_timeout = min(1200.0, max(150.0, 150.0 + size_signal * 0.12))
    phase_1b_timeout = min(480.0, max(120.0, 90.0 + size_signal * 0.06))
    return phase_1a_timeout, phase_1b_timeout


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

    spec_excerpt = _truncate_spec_excerpt(prompt_used)
    loop = asyncio.get_running_loop()
    phase_1a_timeout, phase_1b_timeout = _compute_phase_timeouts(ir, prompt_used)
    entities = ir.entities or []

    # DevOps and Spice generation (unlike Endpoints/BusinessRules/Resilience) don't
    # actually need the finished table list — they only read project_name/tech_stack
    # (see _generate_devops_spec / _generate_spice_spec). On large specs (the same ones
    # that trigger chunked Phase 1A), that metadata is already produced by a small, fast
    # call (_generate_project_meta) independent of the schema-chunk calls — but the
    # previous code waited for the ENTIRE Phase 1A (schema chunks + merge) to finish
    # before starting DevOps/Spice anyway, adding their ~10-40s on top of Phase 1A's
    # own duration instead of hiding it inside it. Starting them the moment that
    # lightweight metadata is known — concurrently with the schema chunks still
    # generating — costs nothing (same calls, same model, same output) and just
    # changes *when* they run. Small/typical specs are untouched: devops_task/spice_task
    # stay None and Phase 1B generates them exactly as before.
    devops_task = None
    spice_task = None
    if _should_chunk_database_spec(entities, spec_excerpt):
        try:
            early_meta = await asyncio.wait_for(
                _generate_project_meta(client, loop, spec_excerpt, ir, feedback_history),
                timeout=60.0
            )
            stub_db_spec = _DatabaseSpec(
                project_name=early_meta.project_name,
                tech_stack=early_meta.tech_stack,
                auth_strategy=early_meta.auth_strategy,
                database=DatabaseSchema(tables=[])
            )
            devops_task = asyncio.create_task(
                _generate_devops_spec(client, loop, spec_excerpt, ir, stub_db_spec, rules, feedback_history)
            )
            spice_task = asyncio.create_task(
                _generate_spice_spec(client, loop, spec_excerpt, ir, stub_db_spec, feedback_history)
            )
            logger.info("[Swarm] Large spec — starting DevOps/Spice generation early, concurrently with Phase 1A.")
        except Exception as e:
            logger.warning(f"[Swarm] Early DevOps/Spice kickoff failed ({e}); will generate them normally in Phase 1B.")
            devops_task = None
            spice_task = None

    # ── Phase 1A: Core Database Spec (Call 1)
    # Own timeout budget, separate from Phase 1B, and now SCALED to spec size instead
    # of one flat number. Flat 450s still timed out live on a 9-module Enterprise spec —
    # small specs finish Phase 1A in 40-90s, but that one measured 251s/288s/>360s/>450s
    # across four consecutive real runs. The model's hidden reasoning cost grows with
    # how many entities it has to reason through and emit, so the budget now grows with
    # entity count instead of chasing a single fixed ceiling.
    logger.info(f"[Swarm] Phase 1A — Generating core Database spec (budget: {phase_1a_timeout:.0f}s)...")
    try:
        db_spec = await asyncio.wait_for(
            _generate_database_spec(client, loop, spec_excerpt, ir, rules, feedback_history),
            timeout=phase_1a_timeout
        )
    except asyncio.TimeoutError:
        if devops_task:
            devops_task.cancel()
        if spice_task:
            spice_task.cancel()
        raise asyncio.TimeoutError(f"Phase 1A (database schema) timed out after {phase_1a_timeout:.0f}s")
    logger.info("[Swarm] Phase 1A complete — core Database spec received.")

    # ── Phase 1B: Concurrent Content Generation (Calls 2-6)
    logger.info(f"[Swarm] Phase 1B — Triggering parallel generation tasks for endpoints, business rules, devops, spice, and resilience (budget: {phase_1b_timeout:.0f}s)...")
    tasks = [
        _generate_endpoints_spec(client, loop, spec_excerpt, ir, db_spec, rules, feedback_history),
        _generate_business_rules_spec(client, loop, spec_excerpt, ir, db_spec, rules, feedback_history),
        devops_task if devops_task is not None else _generate_devops_spec(client, loop, spec_excerpt, ir, db_spec, rules, feedback_history),
        spice_task if spice_task is not None else _generate_spice_spec(client, loop, spec_excerpt, ir, db_spec, feedback_history),
        _generate_resilience_spec(client, loop, spec_excerpt, ir, db_spec, rules, feedback_history)
    ]

    try:
        content_results = await asyncio.wait_for(
            asyncio.gather(*tasks, return_exceptions=True),
            timeout=phase_1b_timeout
        )
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(f"Phase 1B (endpoints/business rules/devops/spice/resilience) timed out after {phase_1b_timeout:.0f}s")
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
    Uses the shared review model (see LLM_REVIEW_MODEL).
    """
    logger.info("DBA Agent reviewing database schema...")
    # Send compact table names + column count only to minimize tokens
    compact_schema = ", ".join(
        [f"{t.name}({len(t.columns)} cols)" for t in database.tables]
    )
    rules_str = "; ".join(rules[:5])  # Only top 5 rules to reduce prompt size
    prompt = f"""Review this DB schema. Tables: {compact_schema}. Rules: {rules_str}."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_REVIEW_MODEL,
            response_model=ReviewResult,
            max_tokens=3000,  # ReviewResult itself is small, but gpt-oss-20b spends most of this on hidden reasoning before the JSON answer
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_DBA_REVIEWER},
                {"role": "user", "content": prompt}
            ]
        )
    )

async def run_security_agent(client: Any, endpoints: List[EndpointSchema], rules: List[str]) -> ReviewResult:
    """
    Security Review Agent: Checks API routes for authentication and vulnerability rules.
    Uses the shared review model (see LLM_REVIEW_MODEL).
    """
    logger.info("Security Agent reviewing API endpoints...")
    # Compact: only list unprotected write endpoints as a concern flag
    unprotected_writes = [f"{e.method} {e.path}" for e in endpoints if not e.is_protected and e.method in ("POST", "PUT", "DELETE", "PATCH")]
    total = len(endpoints)
    prompt = f"""Review {total} API endpoints. Unprotected write endpoints (POST/PUT/DELETE/PATCH): {unprotected_writes or 'None'}."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_REVIEW_MODEL,
            response_model=ReviewResult,
            max_tokens=3000,  # ReviewResult itself is small, but gpt-oss-20b spends most of this on hidden reasoning before the JSON answer
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_SECURITY_REVIEWER},
                {"role": "user", "content": prompt}
            ]
        )
    )

async def run_pm_agent(client: Any, spec: GeneratedArchitectureSpec, prompt_used: str) -> ReviewResult:
    """
    PM Review Agent: Assures the product meets the user's business requirements.
    Uses the shared review model (see LLM_REVIEW_MODEL) with a compact spec summary.
    """
    logger.info("Product Manager reviewing spec against requirements...")
    # Compact spec summary: project name, table names, endpoint paths only
    table_names = ", ".join([t.name for t in spec.database.tables])
    endpoint_paths = ", ".join([f"{e.method} {e.path}" for e in spec.endpoints[:20]])  # cap at 20
    user_prompt_snippet = prompt_used[:500]  # cap to 500 chars
    prompt = f"""User requirements (excerpt): {user_prompt_snippet}
Generated tables: {table_names}
Generated endpoints: {endpoint_paths}"""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_REVIEW_MODEL,
            response_model=ReviewResult,
            max_tokens=3000,  # ReviewResult itself is small, but gpt-oss-20b spends most of this on hidden reasoning before the JSON answer
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_PM_REVIEWER},
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
    
    prompt = f"""System context:
- Archetype: {ir.archetype}
- Project: {spec.project_name}
- Tables: {compact_tables}
- Endpoints: {compact_endpoints}

Tasks:
1. Assign an overall Resilience Rating (A+ to F).
2. Identify 2-3 single points of failure under peak load.
3. Simulate exactly 3 production failure scenarios with mitigation strategies.
4. Provide a 4-step hardening checklist."""

    loop = asyncio.get_running_loop()

    # Run in executor to prevent blocking
    # Uses LLM_REVIEW_MODEL — compact prompt keeps prompt-side tokens low even though the model itself reasons before answering
    result = await loop.run_in_executor(
        None,
        lambda: client.chat.completions.create(
            model=LLM_REVIEW_MODEL,
            response_model=AntiFragilityHardening,
            max_retries=2,
            max_tokens=4000,  # 3 chaos scenarios + checklist, plus gpt-oss-20b's hidden reasoning before the JSON answer
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT_ANTI_FRAGILITY},
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
      1. Architect Agent              — single call, 480s timeout, RAISES on failure (no mock fallback)
      2. Concurrent gather (all 4)    — DBA + Security + PM + Anti-Fragility, 120s timeout
      3. Inject metadata              — always returns a complete real spec
    
    Mock spec is ONLY used when NVIDIA_API_KEY is missing (true offline mode).
    """
    import datetime
    
    client, is_mock = get_instructor_client()
    if is_mock:
        return generate_mock_spec(ir, rules, prompt_used, parent_spec_id, confidence_score, generation_status)

    async def run_review_panel(current_spec: GeneratedArchitectureSpec):
        """Run the review agents plus anti-fragility for a given spec."""
        logger.info("[Swarm] Phase 2 — Dispatching DBA + Security + PM + Anti-Fragility concurrently...")
        results = await asyncio.wait_for(
            asyncio.gather(
                run_dba_agent(client, current_spec.database, rules),
                run_security_agent(client, current_spec.endpoints, rules),
                run_pm_agent(client, current_spec, prompt_used),
                run_anti_fragility_agent(client, current_spec, ir),
                return_exceptions=True
            ),
            timeout=120.0  # gpt-oss-20b's hidden reasoning makes these slower than the old non-reasoning 8B model
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
            # run_architect_agent now scales its own per-phase budgets to spec size
            # (see _compute_phase_timeouts — up to 1200s for Phase 1A + 480s for Phase
            # 1B on the largest specs). This outer wait_for is just a safety net above
            # that worst-case 1680s combined, with margin for scheduling overhead.
            timeout=1750.0
        )
        logger.info("[Swarm] Phase 1 complete — Architect spec received.")
    except asyncio.TimeoutError as e:
        logger.error(f"[Swarm] Architect Agent timed out: {e}. Reporting as failed.")
        raise RuntimeError(f"LLM generation timed out ({e}). Please retry — the NVIDIA API may be under load.")
    except Exception as e:
        # Any other error (Pydantic validation, API error) — also report as failed, do NOT silently return mock
        logger.error(f"[Swarm] Architect Agent failed: {e}. Reporting as failed.")
        raise RuntimeError(f"LLM generation failed: {e}")
    
    # ── Phase 2: Concurrent Review Panel + Anti-Fragility ───────────────────
    # DBA, Security, PM → shared review model (compact prompts, generous max_tokens for hidden reasoning)
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
        # DBA issues mean the schema itself needs rework — Phase 1B (endpoints, business
        # rules, devops, spice, resilience) all reference the table list, so a full
        # revision is the only correct option there. But DBA issues are a small minority
        # of revisions in practice — Security/PM issues (unprotected endpoints, missing
        # requirement coverage) don't touch the schema at all, so redoing all 6 LLM
        # calls for those wastes the 60-90s DB spec call and 3 untouched Phase 1B calls
        # for nothing. Targeted revision regenerates only what was actually flagged.
        dba_failed = not isinstance(dba_res, Exception) and not dba_res.passed
        try:
            if dba_failed:
                logger.info("[Swarm] DBA flagged schema issues — full revision pass (DB spec + all Phase 1B).")
                pre_revision_spec = spec
                pre_revision_table_count = len(pre_revision_spec.database.tables)
                revised_spec = await asyncio.wait_for(
                    run_architect_agent(client, ir, rules, prompt_used, feedback_history=review_issues),
                    # Must exceed run_architect_agent's own internal scaled phase
                    # budgets (up to 1200s + 480s on the largest specs), or this outer
                    # wait_for cuts it off first.
                    timeout=1750.0
                )
                revised_table_count = len(revised_spec.database.tables)
                # A full revision re-derives the ENTIRE schema from the raw prompt in one
                # LLM call — observed live on a 9-module Enterprise spec: the model
                # collapsed a 9-table schema down to a single stub table while "fixing"
                # one flagged column, and the request still returned 200 OK with a
                # near-empty spec. A shrinking table count is a strong, cheap signal that
                # the revision regressed rather than improved, so prefer the pre-revision
                # spec (which is a complete, valid result — just with the flagged issues
                # still present) over a smaller "fixed" one.
                if revised_table_count < pre_revision_table_count:
                    logger.warning(
                        f"[Swarm] Full revision shrank the schema ({pre_revision_table_count} → "
                        f"{revised_table_count} tables). Discarding revision, keeping pre-revision spec."
                    )
                    spec = pre_revision_spec
                else:
                    spec = revised_spec
            else:
                logger.info("[Swarm] Schema is sound — targeted revision pass (endpoints/business rules only).")
                security_failed = not isinstance(sec_res, Exception) and not sec_res.passed
                pm_failed = not isinstance(pm_res, Exception) and not pm_res.passed
                endpoints_feedback = []
                if security_failed:
                    endpoints_feedback.extend(sec_res.issues)
                if pm_failed:
                    endpoints_feedback.extend(pm_res.issues)
                # Reuses the same size-scaled Phase 1B budget computed for the initial
                # pass — endpoints+business_rules is a subset of Phase 1B's work, so it
                # scales with spec size the same way (was a flat 220s, which is too
                # tight for the same large specs that need a scaled Phase 1A budget).
                _, targeted_revision_timeout = _compute_phase_timeouts(ir, prompt_used)
                spec = await asyncio.wait_for(
                    run_targeted_revision(
                        client, ir, rules, prompt_used, spec,
                        endpoints_feedback=endpoints_feedback or None,
                        business_rules_feedback=pm_res.issues if pm_failed else None,
                    ),
                    timeout=targeted_revision_timeout
                )
        except Exception as e:
            # The revision pass is best-effort — `spec` from Phase 1 is already a
            # complete, valid result. Never let a failed *improvement* attempt take
            # down a request that already succeeded once. `spec` is left unchanged
            # (still the pre-revision version) and the review panel below re-runs
            # against it, same as it did in Phase 2.
            logger.warning(f"[Swarm] Revision pass failed ({e}). Keeping the pre-revision spec.")

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
