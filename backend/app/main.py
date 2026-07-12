import logging
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

# Filter out preflight OPTIONS and continuous heartbeat dashboard polling from terminal output
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

# Initialize database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Baxel Backend API",
    description="State-of-the-Art Architecture Specification Generator",
    version="1.0.0"
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
