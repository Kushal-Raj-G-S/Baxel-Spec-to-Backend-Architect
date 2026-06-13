import uuid
import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON, ForeignKey, Boolean
from app.core.db import Base

class ProjectModel(Base):
    """
    SQLAlchemy model for the 'projects' table.
    """
    __tablename__ = "projects"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    workspace_id = Column(String(36), nullable=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    user_id = Column(String(36), nullable=True)


class SpecModel(Base):
    """
    SQLAlchemy model for the 'specs' table, storing user-input specs.
    """
    __tablename__ = "specs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), nullable=False)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    source_type = Column(String(50), default="manual", nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    user_id = Column(String(36), nullable=True)


class PipelineRunModel(Base):
    """
    SQLAlchemy model for the 'pipeline_runs' table, storing visual spec generation details and status.
    """
    __tablename__ = "pipeline_runs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), nullable=False)
    spec_id = Column(String(36), nullable=True)
    status = Column(String(50), nullable=False)
    stages = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    completed_at = Column(DateTime, nullable=True)
    user_id = Column(String(36), nullable=True)


class ProfileModel(Base):
    """
    SQLAlchemy model for the 'profiles' table.
    """
    __tablename__ = "profiles"
    
    id = Column(String(36), primary_key=True)
    email = Column(String(255), nullable=True)
    username = Column(String(255), nullable=True)
    full_name = Column(String(255), nullable=True)
    avatar_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)
    plan_code = Column(String(50), nullable=True)


class PricingPlanModel(Base):
    """
    SQLAlchemy model for the 'pricing_plans' table.
    """
    __tablename__ = "pricing_plans"
    
    id = Column(String(36), primary_key=True)
    code = Column(String(50), nullable=False)
    display_name = Column(String(255), nullable=False)
    price_usd = Column(Integer, nullable=False)
    monthly_project_limit = Column(Integer, nullable=False)
    monthly_run_limit = Column(Integer, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow, nullable=False)


class ChatMessageModel(Base):
    """
    SQLAlchemy model for the 'chat_messages' table, storing chatbot queries and responses.
    """
    __tablename__ = "chat_messages"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    spec_id = Column(String(36), nullable=False)
    user_id = Column(String(36), nullable=True)
    query = Column(Text, nullable=False)
    response = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

