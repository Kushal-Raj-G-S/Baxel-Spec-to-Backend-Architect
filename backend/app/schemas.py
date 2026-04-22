from datetime import datetime
from typing import List, Dict, Any
from pydantic import BaseModel, Field


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None


class Project(ProjectCreate):
    id: str
    created_at: datetime


class ProjectHistoryRunItem(BaseModel):
    id: str
    status: str
    created_at: datetime
    spec_id: str | None = None
    spec_title: str | None = None
    result: Dict[str, Any] | None = None


class ProjectHistory(BaseModel):
    project: Project
    specs_count: int
    pipeline_runs_count: int
    recent_runs: List[ProjectHistoryRunItem] = Field(default_factory=list)


class SpecCreate(BaseModel):
    project_id: str
    title: str
    content: str


class Spec(SpecCreate):
    id: str
    created_at: datetime


class PipelineRunRequest(BaseModel):
    project_id: str
    spec_id: str
    stack: str = Field(default="fastapi+supabase")


class PipelineRunResponse(BaseModel):
    id: str
    status: str
    result: Dict[str, Any] | None = None


class PipelineStatus(BaseModel):
    id: str
    status: str
    stages: List[Dict[str, str]]
    result: Dict[str, Any] | None = None


class PipelineRunListItem(BaseModel):
    id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    project_name: str | None = None
    spec_title: str | None = None
    duration_seconds: int | None = None


class DashboardProjectItem(BaseModel):
    id: str
    name: str
    created_at: datetime


class DashboardPipelineItem(BaseModel):
    id: str
    status: str
    created_at: datetime
    spec_title: str | None = None
    project_name: str | None = None


class DashboardSummary(BaseModel):
    projects_count: int
    specs_count: int
    pipeline_runs_count: int
    recent_projects: List[DashboardProjectItem] = Field(default_factory=list)
    recent_pipeline_runs: List[DashboardPipelineItem] = Field(default_factory=list)


class PublicMetrics(BaseModel):
    specs_processed: int
    schemas_generated: int
    api_endpoints: int
    rules_captured: int


class PlanSummary(BaseModel):
    plan_name: str = "Starter"
    plan_code: str = "starter"
    status: str = "active"
    monthly_run_limit: int = 9
    runs_used_this_month: int = 0
    monthly_project_limit: int = 3
    projects_used_this_month: int = 0
    runs_per_project_limit: int = 3
    idea_char_limit: int = 1000
    billing_period: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None
    manage_url: str | None = None


class ShareTokenResponse(BaseModel):
    token: str


class SharedRunResponse(BaseModel):
    run_id: str
    status: str
    created_at: datetime
    project_name: str | None = None
    spec_title: str | None = None
    result: Dict[str, Any] | None = None


class ProfileResponse(BaseModel):
    id: str
    email: str | None = None
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None


class ProfileUpdate(BaseModel):
    username: str | None = None
    full_name: str | None = None
    avatar_url: str | None = None
