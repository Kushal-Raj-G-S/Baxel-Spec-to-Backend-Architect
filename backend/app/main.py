import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.routers import dashboard, pipeline, profile, projects, runs, specs

logging.basicConfig(
    level=getattr(logging, settings.log_level, logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s request_id=%(request_id)s %(message)s",
)


class RequestIdFilter(logging.Filter):
    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = "-"
        return True


for logger_name in ["app", "uvicorn", "uvicorn.access", "uvicorn.error"]:
    logging.getLogger(logger_name).addFilter(RequestIdFilter())

logger = logging.getLogger("app.main")

app = FastAPI(title="Baxel API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins,
    allow_origin_regex=r"https?://(localhost|127\.0\.0\.1)(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


@app.get("/health")
def health_check():
    return {"status": "ok"}


@app.middleware("http")
async def log_requests(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid.uuid4())
    start = time.perf_counter()
    logger.info(
        "request.start method=%s path=%s",
        request.method,
        request.url.path,
        extra={"request_id": request_id},
    )
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["x-request-id"] = request_id
    logger.info(
        "request.end method=%s path=%s status=%s duration_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed_ms,
        extra={"request_id": request_id},
    )
    return response


app.include_router(projects.router)
app.include_router(specs.router)
app.include_router(pipeline.router)
app.include_router(dashboard.router)
app.include_router(profile.router)
app.include_router(runs.router)
