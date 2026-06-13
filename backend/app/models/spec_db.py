import uuid
import datetime
from sqlalchemy import Column, String, Integer, Text, DateTime, JSON
from app.core.db import Base

class SpecModel(Base):
    """
    SQLAlchemy model for the 'specs' table, capturing full generation history,
    parent spec relationships (for iteration), versioning, and prompt metadata.
    """
    __tablename__ = "specs"
    
    # Using 36-char string for compatibility with both PostgreSQL UUID and SQLite Text
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), nullable=True)
    parent_spec_id = Column(String(36), nullable=True)
    version = Column(Integer, default=1, nullable=False)
    prompt_used = Column(Text, nullable=False)
    generated_json = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
