import os
import logging
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

load_dotenv(override=True)
logger = logging.getLogger(__name__)


def _resolve_database_url() -> str:
    """
    Resolves the database URL with cloud-production-safe settings:

    1. Direct Supabase connections (port 5432) are auto-upgraded to the
       PgBouncer Transaction Mode Pooler (port 6543). This allows many
       parallel cloud workers to share a small connection pool without
       exhausting Postgres connection limits.

    2. Falls back to local SQLite when SUPABASE_DB_URL is not set
       (local development / offline mode).
    """
    url = os.getenv("SUPABASE_DB_URL", "").strip()

    if url:
        # Upgrade direct connection → PgBouncer pooler (transaction mode)
        # Supabase pooler hostnames contain ".pooler.supabase.com"
        # Direct port 5432 → Pooler port 6543
        if ".pooler.supabase.com:5432" in url:
            url = url.replace(":5432/", ":6543/")
            logger.info(
                "DB: Upgraded Supabase connection to PgBouncer Pooler "
                "(port 5432 → 6543, transaction mode)."
            )

        # SQLAlchemy requires postgresql:// → postgresql+psycopg2://
        if url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg2://", 1)

        return url

    # Local SQLite fallback
    workspace_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../..")
    )
    db_path = os.path.join(workspace_dir, "baxel.db")
    logger.info(f"SUPABASE_DB_URL not found. Using local SQLite at {db_path}")
    return f"sqlite:///{db_path}"


DATABASE_URL = _resolve_database_url()
Base = declarative_base()

try:
    # pool_pre_ping=True: validates connections before use (handles dropped pooler connections)
    # pool_size / max_overflow: safe limits for cloud worker concurrency
    engine = create_engine(
        DATABASE_URL,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=(
            {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}
        ),
    )
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
except Exception as e:
    logger.error(
        f"Failed to create SQLAlchemy engine for {DATABASE_URL}: {e}. "
        "Falling back to local SQLite."
    )
    workspace_dir = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "../../..")
    )
    db_path = os.path.join(workspace_dir, "baxel.db")
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
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
