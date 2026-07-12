import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv(override=True)
logger = logging.getLogger(__name__)

# Fetch database URL, defaulting to workspace SQLite for easy local dev
DATABASE_URL = os.getenv("SUPABASE_DB_URL")
if DATABASE_URL:
    # SQLAlchemy requires postgresql:// to be postgresql+psycopg2:// or similar
    if DATABASE_URL.startswith("postgresql://"):
        DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)
else:
    # Store sqlite in the workspace folder
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    db_path = os.path.join(workspace_dir, "baxel.db")
    DATABASE_URL = f"sqlite:///{db_path}"
    logger.info(f"SUPABASE_DB_URL not found. Using local SQLite at {db_path}")

Base = declarative_base()

try:
    engine = create_engine(DATABASE_URL, pool_pre_ping=True)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.error(f"Failed to create SQLAlchemy engine for {DATABASE_URL}: {e}. Falling back to local SQLite.")
    workspace_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
    db_path = os.path.join(workspace_dir, "baxel.db")
    engine = create_engine(f"sqlite:///{db_path}")
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def get_db():
    """
    FastAPI dependency that yields a database session.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
