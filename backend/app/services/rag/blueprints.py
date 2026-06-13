from typing import List, Dict, Any
from pathlib import Path
import json

# Seed blueprints representing the 10 core baseline archetypes for Baxel MVP.
# These will be embedded and loaded into the Faiss index.
BLUEPRINTS: List[Dict[str, Any]] = [
    {
        "archetype": "B2B Multi-tenant SaaS",
        "rules": [
            "Tenant Isolation: MUST use a shared database with a tenant_id column on every table.",
            "Row-Level Security (RLS): MUST enforce tenant_id filters in all queries or use DB-level RLS policies.",
            "Scalability: Database indexes MUST include tenant_id composite keys for performance."
        ],
        "anti_patterns": [
            "Do NOT create separate database schemas or physical databases per tenant at this scale.",
            "Do NOT store tenant context in client-side cookies or trust tenant_id from request bodies without verification."
        ],
        "recommended_stack": {
            "language": "Python",
            "framework": "FastAPI",
            "database_engine": "PostgreSQL",
            "cache": "Redis"
        }
    },
    {
        "archetype": "E-commerce Marketplace",
        "rules": [
            "Transactional Safety: MUST use atomic database transactions for checkout and order flows.",
            "Idempotency: MUST enforce idempotency keys on payment endpoints to avoid double-charging.",
            "Webhooks: Stripe checkout webhooks MUST verify signature and process events asynchronously."
        ],
        "anti_patterns": [
            "Do NOT perform stock deductions without locking rows (avoid race conditions).",
            "Do NOT store raw credit card details on your database (use Stripe Tokens instead)."
        ],
        "recommended_stack": {
            "language": "TypeScript",
            "framework": "Next.js",
            "database_engine": "PostgreSQL",
            "cache": "Redis"
        }
    },
    {
        "archetype": "Real-time Collaborative App",
        "rules": [
            "State Synchronization: MUST use WebSockets for bi-directional communication.",
            "Pub/Sub: MUST use a Redis Pub/Sub backplane to broadcast WebSocket events across multiple server instances.",
            "Conflict Resolution: Enforce Operational Transformation (OT) or CRDTs for collaborative document editing."
        ],
        "anti_patterns": [
            "Do NOT poll REST endpoints for real-time state updates (scales terribly).",
            "Do NOT maintain in-memory WebSocket connections on a single node without a shared pub/sub layer."
        ],
        "recommended_stack": {
            "language": "TypeScript",
            "framework": "NestJS",
            "database_engine": "MongoDB",
            "cache": "Redis"
        }
    },
    {
        "archetype": "Video Streaming & Transcoding",
        "rules": [
            "Event-Driven: Video uploads MUST emit an event to a message broker (RabbitMQ/SQS).",
            "Async Processing: Transcoding tasks MUST run on background workers (Celery) separated from the core API.",
            "Secure Storage: Videos MUST be served via CDN URLs (CloudFront/Cloudflare) using signed URLs for access control."
        ],
        "anti_patterns": [
            "Do NOT perform heavy video transcoding synchronously within the API request thread.",
            "Do NOT serve raw video files directly from the web server or primary database."
        ],
        "recommended_stack": {
            "language": "Python",
            "framework": "FastAPI",
            "database_engine": "PostgreSQL",
            "cache": "Redis"
        }
    },
    {
        "archetype": "Social Network / Graph-based App",
        "rules": [
            "Graph Modeling: Feed generation MUST utilize graph relationships (e.g. Followers, Friends).",
            "Caching: Newsfeeds MUST be pre-calculated and cached in Redis for fast retrieval.",
            "Pagination: All feed endpoints MUST implement cursor-based pagination to support infinite scroll."
        ],
        "anti_patterns": [
            "Do NOT use expensive SQL JOINs across massive tables to generate real-time social feeds.",
            "Do NOT fetch the entire user feed list without a strict limit."
        ],
        "recommended_stack": {
            "language": "TypeScript",
            "framework": "Express",
            "database_engine": "Neo4j",
            "cache": "Redis"
        }
    },
    {
        "archetype": "AI / Data Processing Pipeline",
        "rules": [
            "Queue Isolation: Task queues (RabbitMQ/Celery) MUST isolate heavy model inference tasks from standard tasks.",
            "Rate Limiting: Enforce strict API rate-limiting per client using Redis token bucket.",
            "Fault Tolerance: Implement retries with exponential backoff for external LLM API calls."
        ],
        "anti_patterns": [
            "Do NOT block the main thread waiting for slow machine learning models to respond.",
            "Do NOT run heavy data cleaning scripts inside the API request-response loop."
        ],
        "recommended_stack": {
            "language": "Python",
            "framework": "FastAPI",
            "database_engine": "PostgreSQL",
            "cache": "Redis"
        }
    },
    {
        "archetype": "IoT / Time-Series Dashboard",
        "rules": [
            "Optimized Ingestion: Ingestion endpoints MUST be lightweight and process payloads asynchronously.",
            "Specialized Storage: MUST use time-series optimized storage engines (TimescaleDB/InfluxDB) for metrics.",
            "Retention Policies: Enforce strict DB roll-up and metric downsampling retention rules."
        ],
        "anti_patterns": [
            "Do NOT use standard relational table structures without partitioning for raw high-frequency telemetry data.",
            "Do NOT perform raw aggregation queries on database tables with millions of rows on page load."
        ],
        "recommended_stack": {
            "language": "Go",
            "framework": "Gin",
            "database_engine": "TimescaleDB",
            "cache": "Redis"
        }
    },
    {
        "archetype": "Financial Ledger / Fintech App",
        "rules": [
            "Double-Entry: MUST implement strict double-entry ledger rules (debits and credits must balance).",
            "Immutability: Financial transaction logs MUST be read-only (updates or deletions are prohibited).",
            "Audit Trail: All transaction edits MUST generate a new adjustment log with audit user ID metadata."
        ],
        "anti_patterns": [
            "Do NOT store account balances as simple editable fields without a transaction log backing them.",
            "Do NOT perform currency calculations using floating-point types (use Decimal/integers)."
        ],
        "recommended_stack": {
            "language": "Python",
            "framework": "FastAPI",
            "database_engine": "PostgreSQL",
            "cache": "Redis"
        }
    },
    {
        "archetype": "Healthcare SaaS",
        "rules": [
            "Data Encryption: Encrypt PHI (Protected Health Information) data at rest using AES-256.",
            "Detailed Audit Logs: Enforce HIPAA-compliant access logs capturing every read/write action on patient tables.",
            "Strict Auth: Session tokens MUST expire quickly, requiring re-authentication."
        ],
        "anti_patterns": [
            "Do NOT print PHI data in stdout or log files (e.g. traceback, debug statement logs).",
            "Do NOT deploy HIPAA-regulated databases to uncertified hardware layers."
        ],
        "recommended_stack": {
            "language": "TypeScript",
            "framework": "NestJS",
            "database_engine": "PostgreSQL",
            "cache": "Redis"
        }
    },
    {
        "archetype": "General SaaS",
        "rules": [
            "MVC Pattern: Structure backend logic into routers, services, and models layers.",
            "Relational Storage: Use PostgreSQL with structured foreign keys and indexes.",
            "Standard Auth: Enforce JWT authentication with password hashing (bcrypt/argon2)."
        ],
        "anti_patterns": [
            "Do NOT write business logic directly inside the routing layer (keep it in service layer).",
            "Do NOT expose auto-incrementing integer database IDs on your public API endpoints (use UUIDs)."
        ],
        "recommended_stack": {
            "language": "Python",
            "framework": "FastAPI",
            "database_engine": "PostgreSQL",
            "cache": "Redis"
        }
    }
]

# Dynamically load generated blueprints from knowledge_hub outputs
try:
    outputs_dir = Path(__file__).parents[3] / "knowledge_hub" / "outputs"
    if outputs_dir.exists() and outputs_dir.is_dir():
        for json_file in outputs_dir.glob("**/*.json"):
            try:
                data = json.loads(json_file.read_text(encoding="utf-8"))
                if (
                    isinstance(data, dict)
                    and "archetype" in data
                    and "rules" in data
                    and "anti_patterns" in data
                    and "recommended_stack" in data
                ):
                    # Clean/validate rules and anti_patterns to be list of strings
                    if isinstance(data["rules"], list) and isinstance(data["anti_patterns"], list):
                        # Avoid duplicating seed blueprints by name
                        if not any(bp["archetype"].strip().lower() == data["archetype"].strip().lower() for bp in BLUEPRINTS):
                            BLUEPRINTS.append(data)
            except Exception:
                pass
except Exception:
    pass

