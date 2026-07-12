import logging
from contextlib import asynccontextmanager
from dotenv import load_dotenv
load_dotenv(override=True)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.endpoints import generate, chat
from app.api.endpoints.dashboard_api import (
    projects_router,
    specs_router,
    pipelines_router,
    dashboard_router,
    profile_router,
    runs_router
)
from app.core.db import Base, engine
from app.models.spec_db import SpecModel

# -------------------------------------------------------------
# Clean Logging Configuration
# -------------------------------------------------------------
# Silence verbose third-party loggers
logging.getLogger("faiss").setLevel(logging.WARNING)
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("huggingface_hub").setLevel(logging.WARNING)
logging.getLogger("openai").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("httpx").setLevel(logging.WARNING)

# Filter out preflight OPTIONS and continuous heartbeat dashboard polling
class CleanAccessLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        msg = record.getMessage()
        if "OPTIONS " in msg:
            return False
        if "GET /profile/" in msg:
            return False
        if "GET /dashboard/summary" in msg:
            return False
        if "GET /dashboard/public-metrics" in msg:
            return False
        return True

logging.getLogger("uvicorn.access").addFilter(CleanAccessLogFilter())

logger = logging.getLogger(__name__)

# Initialize database tables
Base.metadata.create_all(bind=engine)


# -------------------------------------------------------------
# Startup Lifespan — Pre-Warm All Services
# -------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI startup lifespan that initializes all cloud services ONCE when
    the server boots, rather than lazily on the first request.

    This eliminates:
    - The ~14s HuggingFace weight loading delay on request 1
    - The "Index is not ready" semantic-router warning
    - Cold start lag from uninitialized Faiss indexes

    All services use the shared CloudEmbedder (Nvidia NIM API),
    so initialization is a fast API health-check (~0.8s) rather than
    a disk read (~14s).
    """
    logger.info("[Startup] Pre-warming cloud services...")

    # 1. Initialize CloudEmbedder first (shared singleton)
    try:
        from app.services.nlp.cloud_embedder import cloud_embedder
        cloud_embedder.initialize()
        logger.info("[Startup] CloudEmbedder ready.")
    except Exception as e:
        logger.warning(f"[Startup] CloudEmbedder init failed: {e}")

    # 2. Initialize RAG Vector DB (embeds all 10 blueprints in one batch call)
    try:
        from app.services.rag.retriever import rag_retriever
        rag_retriever.initialize()
        logger.info("[Startup] RAG Vector DB ready.")
    except Exception as e:
        logger.warning(f"[Startup] RAG retriever init failed: {e}")

    # 3. Initialize Semantic Clustering
    try:
        from app.services.nlp.clustering import semantic_clustering
        semantic_clustering.initialize()
        logger.info("[Startup] Semantic Clustering ready.")
    except Exception as e:
        logger.warning(f"[Startup] Semantic Clustering init failed: {e}")

    # 4. Initialize Semantic Router
    try:
        from app.services.nlp.router import semantic_router
        semantic_router.initialize()
        logger.info("[Startup] Semantic Router ready.")
    except Exception as e:
        logger.warning(f"[Startup] Semantic Router init failed: {e}")

    logger.info("[Startup] All services pre-warmed. Server is ready.")
    yield
    # Shutdown (nothing to clean up for stateless cloud API connections)
    logger.info("[Shutdown] Baxel server shutting down.")


app = FastAPI(
    title="Baxel Backend API",
    description="State-of-the-Art Architecture Specification Generator",
    version="1.0.0",
    lifespan=lifespan,
)

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(generate.router, prefix="/api", tags=["generation"])
app.include_router(chat.router, prefix="/api", tags=["chatbot"])
app.include_router(projects_router)
app.include_router(specs_router)
app.include_router(pipelines_router)
app.include_router(dashboard_router)
app.include_router(profile_router)
app.include_router(runs_router)


@app.get("/")
async def root():
    return {"message": "Baxel API is running."}
