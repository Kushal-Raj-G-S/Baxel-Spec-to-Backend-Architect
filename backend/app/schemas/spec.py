from typing import List, Optional
from pydantic import BaseModel, Field

# -----------------------------------------
# Metadata & Tech Stack
# -----------------------------------------

class SpecMetadata(BaseModel):
    version: str = Field(..., description="The version of the generated spec, e.g., '1.0.0'")
    parent_spec_id: Optional[str] = Field(None, description="The UUID of the parent spec this was iterated from")
    created_at: str = Field(..., description="ISO timestamp of when this spec was generated")
    prompt_used: str = Field(..., description="The exact raw prompt the user provided, used for iteration")
    confidence_score: Optional[float] = Field(None, description="Confidence score from the semantic router, if applicable")
    generation_status: str = Field(default="complete", description="Status of the generation: 'complete' or 'partial'")

class TechStack(BaseModel):
    language: str = Field(..., description="Programming language, e.g., 'Python', 'TypeScript'")
    framework: str = Field(..., description="Backend framework, e.g., 'FastAPI', 'Express', 'NestJS'")
    database_engine: str = Field(..., description="Primary database, e.g., 'PostgreSQL', 'MongoDB'")
    cache: Optional[str] = Field(None, description="Caching layer if needed, e.g., 'Redis'")

class AuthStrategy(BaseModel):
    method: str = Field(..., description="Authentication method, e.g., 'JWT', 'OAuth2', 'API_KEY', 'Session'")
    token_expiry_seconds: Optional[int] = Field(None, description="Lifespan of the token in seconds, if applicable")
    refresh_token_supported: bool = Field(default=False, description="Whether refresh tokens are used")

# -----------------------------------------
# Core Fundamentals: Database Schema
# -----------------------------------------

class ColumnSchema(BaseModel):
    name: str = Field(..., description="The name of the database column, e.g., 'id' or 'created_at'")
    type: str = Field(..., description="The data type of the column, e.g., 'UUID', 'String', 'DateTime', 'Boolean'")
    is_primary_key: bool = Field(default=False, description="True if this is the primary key")
    is_nullable: bool = Field(default=False, description="True if the column can be null")
    foreign_key: Optional[str] = Field(None, description="If this is a foreign key, the 'table.column' it references")

class TableSchema(BaseModel):
    name: str = Field(..., description="The name of the table, e.g., 'users' or 'invoices'")
    description: str = Field(..., description="A short explanation of what this table stores")
    columns: List[ColumnSchema] = Field(..., description="The list of columns in this table")

class DatabaseSchema(BaseModel):
    tables: List[TableSchema] = Field(..., description="All the database tables required for the architecture")

# -----------------------------------------
# Core Fundamentals: API Endpoints
# -----------------------------------------

class EndpointSchema(BaseModel):
    method: str = Field(..., description="The HTTP method, e.g., 'GET', 'POST', 'PUT', 'DELETE'")
    path: str = Field(..., description="The API route, e.g., '/api/v1/users'")
    summary: str = Field(..., description="A brief summary of what the endpoint does")
    is_protected: bool = Field(..., description="True if the endpoint requires authentication")
    request_payload_schema: Optional[str] = Field(None, description="Brief description of the expected request body fields")
    response_payload_schema: Optional[str] = Field(None, description="Brief description of the successful response fields")
    error_responses: Optional[List[str]] = Field(None, description="List of possible HTTP error status codes, e.g., ['401', '404']")

# -----------------------------------------
# The Spice Layer & Simple Premium Features
# -----------------------------------------

class BusinessRule(BaseModel):
    rule: str = Field(..., description="A specific business logic constraint, e.g., 'Users cannot be deleted if they have unpaid invoices'")
    reason: str = Field(..., description="Why this rule is necessary based on the user's prompt")

class SpiceLayer(BaseModel):
    devils_advocate: str = Field(..., description="A playful but accurate warning about where this architecture might break at scale.")
    design_rationale: str = Field(..., description="An explanation of why the AI chose this specific stack or design pattern.")
    estimated_time_saved_hours: int = Field(..., description="Estimated hours of boilerplate writing the user just saved.")

class DevOpsSetup(BaseModel):
    environment_variables: List[str] = Field(..., description="A list of the .env keys needed")
    dockerfile_content: str = Field(..., description="A ready-to-use Dockerfile string")
    docker_compose_content: Optional[str] = Field(None, description="Optional docker-compose.yml for running db alongside backend")

# -----------------------------------------
# Anti-Fragility & Chaos Simulation Schema
# -----------------------------------------

class ChaosFailureScenario(BaseModel):
    scenario_name: str = Field(..., description="E.g., 'Acoustic Telemetry Latency Spike' or 'Ledger DB Lock'")
    failure_description: str = Field(..., description="Detailed description of what fails under load or outage")
    impact_analysis: str = Field(..., description="What happens to the endpoints/data when this failure occurs")
    mitigation_strategy: str = Field(..., description="Specific implementation design to survive this failure (e.g. queue buffering, circuit-breakers)")

class AntiFragilityHardening(BaseModel):
    resilience_rating: str = Field(..., description="Overall resilience score, e.g., 'A', 'B-', 'C+'")
    critical_vulnerabilities: List[str] = Field(..., description="List of single points of failure in this architecture")
    chaos_scenarios: List[ChaosFailureScenario] = Field(..., description="Simulated failure scenarios and mitigations")
    hardening_checklist: List[str] = Field(..., description="Step-by-step developer actions to make this production-ready")

# -----------------------------------------
# Master Output Schema
# -----------------------------------------

class GeneratedArchitectureSpec(BaseModel):
    """
    The master Pydantic schema that the LLM will be forced to output.
    """
    metadata: SpecMetadata
    project_name: str = Field(..., description="A catchy name for the project")
    tech_stack: TechStack
    auth_strategy: AuthStrategy
    database: DatabaseSchema
    endpoints: List[EndpointSchema]
    business_rules: List[BusinessRule]
    devops: DevOpsSetup
    spice: SpiceLayer
    anti_fragility: Optional[AntiFragilityHardening] = Field(None, description="Chaos engineering and resilience hardening audit")

# -----------------------------------------
# Internal Agent Schemas (Not for UI)
# -----------------------------------------

class ReviewResult(BaseModel):
    """
    Schema used by the internal AI Review Panel (DBA, Security) to provide structured feedback back to the Architect Agent.
    """
    passed: bool = Field(..., description="True if the draft passes this agent's strict review")
    issues: List[str] = Field(default_factory=list, description="Specific issues found in the draft")
    suggested_fixes: List[str] = Field(default_factory=list, description="Specific instructions on how to fix the issues")

# -----------------------------------------
# Intermediate & Pipeline Schemas
# -----------------------------------------

class IntermediateRepresentation(BaseModel):
    """
    Schema for the IR created after Phase 1 entity extraction, used to query the vector DB.
    """
    actors: List[str] = Field(default_factory=list, description="The key user roles or actors identified")
    entities: List[str] = Field(default_factory=list, description="Core domain entities extracted")
    implied_integrations: List[str] = Field(default_factory=list, description="Integrations inferred from entities")
    archetype: str = Field(..., description="The primary system archetype classified")

class BlueprintDocument(BaseModel):
    """
    Schema representing the structure of a blueprint stored in the vector DB.
    """
    archetype: str = Field(..., description="The archetype this blueprint applies to")
    rules: List[str] = Field(..., description="Must-have constraints for this archetype")
    anti_patterns: List[str] = Field(..., description="Things to strictly avoid for this archetype")
    recommended_stack: TechStack = Field(..., description="The baseline recommended stack")
