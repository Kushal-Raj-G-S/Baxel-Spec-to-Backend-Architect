<div align="center">

<img src="frontend/public/logo.png" width="120" alt="Baxel Logo"/>

# Baxel

### 🏗️ From messy product specs to production-ready backend architecture — in minutes.

<p align="center">
  Baxel transforms unstructured product ideas into complete, reviewed, and production-grade backend blueprints through a multi-agent AI swarm, RAG-powered archetype matching, and an intelligent spec-aware chatbot.
</p>

<br/>

<p align="center">
  <img src="https://img.shields.io/badge/Next.js-Frontend-000000?style=for-the-badge&logo=nextdotjs&logoColor=white"/>
  <img src="https://img.shields.io/badge/FastAPI-Backend-009688?style=for-the-badge&logo=fastapi&logoColor=white"/>
  <img src="https://img.shields.io/badge/Supabase-Auth%20%26%20DB-3ECF8E?style=for-the-badge&logo=supabase&logoColor=white"/>
  <img src="https://img.shields.io/badge/NVIDIA%20NIM-LLM%20API-76B900?style=for-the-badge&logo=nvidia&logoColor=white"/>
  <img src="https://img.shields.io/badge/PostgreSQL-SQLAlchemy-4169E1?style=for-the-badge&logo=postgresql&logoColor=white"/>
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
  <img src="https://img.shields.io/badge/TypeScript-Strict-3178C6?style=for-the-badge&logo=typescript&logoColor=white"/>
</p>

<p align="center">
  <a href="#-why-baxel">Why Baxel</a> •
  <a href="#-features">Features</a> •
  <a href="#-architecture">Architecture</a> •
  <a href="#%EF%B8%8F-the-agent-swarm">Agent Swarm</a> •
  <a href="#-sage-chatbot">SAGE</a> •
  <a href="#-local-setup">Setup</a> •
  <a href="#-database-schema">Database</a>
</p>

</div>

---

# 💡 Why Baxel?

Most AI coding tools start *after* architecture is already decided. Baxel solves the stage **before** coding begins.

Product ideas come in as messy, unstructured text. Figuring out entities, relationships, auth patterns, database schemas, API surfaces, DevOps config, and resilience concerns takes **days of engineering effort** — even before a single line of code is written.

Baxel compresses that into minutes by running your idea through a full multi-agent reasoning pipeline:

- 🧠 **NLP extraction** — identifies actors, entities, and integrations from raw text
- 📚 **RAG archetype matching** — retrieves the best design blueprint for your system type
- 🤖 **Agent swarm** — Architect, DBA, Security, PM, and Anti-Fragility agents debate the design
- 💬 **SAGE chatbot** — a spec-aware AI assistant that answers questions about your generated architecture
- 📦 **ZIP Scaffold Export** — download a NestJS or FastAPI project, with working auth and CRUD, that installs and starts

This project was built with a **product-first engineering mindset**:

- ⚡ Real LLM generation — no templates, no compromises
- 🏗️ Full multi-agent pipeline with structured output enforcement
- 📊 PostgreSQL persistence for every project, run, and chat message
- 🎨 Premium dark-mode glassmorphism UI with real-time progress feedback
- 🔐 Multi-tenant auth, plan-gating, and quota enforcement

---

# ✨ Features

## 🧠 Multi-Agent Architecture Swarm
- **Principal Architect Agent** (`nemotron-3-ultra-550b`) drafts a complete system design — schema, endpoints, business rules, DevOps, resilience
- **DBA Agent** reviews schema for normalization, foreign keys, and tenant isolation
- **Security Agent** audits API endpoints for authentication coverage
- **PM Agent** validates the spec matches the original product requirements
- **Anti-Fragility Agent** simulates chaos scenarios and generates a hardening checklist
- All review agents run **concurrently** after the Architect draft

## 🔍 Cloud-Native NLP Pipeline (Flow A + Flow B)
- **Intent gate** rejects prompts that are not software specs. A keyword check makes this call today: the `semantic-router` integration loads, but its index is not synced, and forcing it on rejected valid specs in testing
- **GLiNER / LLM-based Entity Extractor** pulls actors, domain entities, and integration names
- **Semantic Clustering** merges synonym entities (e.g. "Customer", "Client" → canonical form)
- **RAG Blueprint Retriever** (Faiss + CloudEmbedder) matches your system to the best-fit archetype blueprint
- **0.75s Latency Embeddings**: Employs `nvidia/llama-nemotron-embed-vl-1b-v2` cloud embeddings and pre-loaded indices on boot, slashing pre-processing time from **16s to under 3s**.

## 💬 SAGE — Specification Answering & Guidance Engine
- A dedicated spec-aware AI chatbot embedded in the platform
- Automatically loads your latest generated spec as context
- **70% Context-Pruning Optimization**: Excludes verbose DevOps scripts and Chaos logs unless relevant, which keeps the prompt small.
- **Grounding & Consistency Checkers**: Automatically audits query premises against both the Original User Prompt and the output JSON schema, flagging mismatches as the first line of responses.
- Maintains **5-turn conversation memory** persisted in the database.

## 📦 One-Click Runnable Scaffold
Downloads a NestJS or FastAPI project that matches the generated spec, ready to install and start:
```bash
scaffold.zip/
├── Dockerfile, docker-compose.yml
├── .env                     # random JWT secret generated per download
├── migrations/schema.sql    # idempotent, applied automatically on startup
├── NestJS:  src/main.ts, app.module.ts, app.controller.ts, crud.service.ts, auth/, entities/
└── FastAPI: app/main.py, app/core/{db,crud,auth}.py, app/models/, app/routes/
```
- **Implemented for you**: register, login and refresh (bcrypt hashes, access + refresh JWTs), plus list/get/create/update/delete for resources, including `/me` and nested routes
- **Safe by default**: password hashes are never returned or writable, `id` and timestamps can't be set from a request body, and rows that belong to an account are filtered to that account
- **Left for you**: business actions such as payments, refunds and status changes return `501` with their request and response notes as comments
- **How much is implemented depends on the spec**: 19 of 41 to 38 of 43 endpoints across the projects tested
- **Tested end to end**: generated NestJS and FastAPI apps passed 63 checks using their real startup code against PostgreSQL. Docker builds have not been tested

## 💎 Plans
Plans limit how much you can run, not the quality of the output. Every tier uses the same model and the full agent swarm.

| Plan | Price | Runs / month | Projects | Prompt length | SAGE messages |
|---|---|---|---|---|---|
| **Free** | $0 | 3 | 3 | 3,000 characters | 15 / day |
| **Pro** | $14 | 25 | 15 | 6,000 characters | Unlimited |
| **Team** | $45 | 100 | 50 | 10,000 characters | Unlimited |
| **Enterprise** | Custom | Custom | Custom | 100,000 characters | Unlimited |

Limits are enforced by `PLAN_LIMITS` in `app/api/endpoints/dashboard_api.py`. The `pricing_plans` table only overrides display names. Profiles still holding the older `starter`, `creator`, `studio` or `growth` codes are mapped onto these tiers.

---

# 🏗 Architecture

```mermaid
graph TD
    User([User]) --> FE[Next.js Frontend]

    FE --> Auth[Supabase Auth]
    FE --> API[FastAPI Backend]

    subgraph Pipeline["🤖 Generation Pipeline"]
        API --> NLP[NLP Pipeline]
        NLP --> EntityExtractor[GLiNER or LLM Entity Extractor]
        NLP --> SemanticRouter[Intent Check]
        NLP --> Clustering[Semantic Clustering]
        NLP --> RAG[RAG Blueprint Retriever]
        RAG --> Faiss[(Faiss Index)]
        RAG --> Blueprints[(10 Archetype Blueprints)]

        API --> Swarm[Agent Swarm]
        Swarm --> Architect[Architect Agent]
        Architect --> Reviews[Concurrent Review Panel]
        Reviews --> DBA[DBA Agent]
        Reviews --> Security[Security Agent]
        Reviews --> PM[PM Agent]
        Reviews --> AntiFragility[Anti-Fragility Agent]
    end

    subgraph Storage["🗄️ PostgreSQL - Supabase"]
        DB[(projects)]
        DB2[(specs)]
        DB3[(pipeline_runs)]
        DB4[(chat_messages)]
        DB5[(profiles)]
        DB6[(pricing_plans)]
        DB7[(workspaces)]
        DB8[(user_preferences)]
    end

    API --> Storage
    FE --> SAGE[SAGE Chatbot]
    SAGE --> API

    subgraph LLM["⚡ NVIDIA NIM API"]
        LLMModel[nemotron-3-ultra-550b]
        EmbedModel[nvidia/llama-nemotron-embed-vl-1b-v2]
    end

    Architect --> LLMModel
    Reviews --> LLMModel
    EntityExtractor --> LLMModel
    NLP --> EmbedModel
    SAGE --> LLMModel
```

---

# ⚙️ The Agent Swarm

The generation pipeline runs in three phases:

### Phase 1 — Intent check, then NLP & RAG (concurrent)
An intent check rejects prompts that are not software specs, then two flows run at once:
*   **Flow A**: Entity extraction (GLiNER when installed, otherwise LLM and rule-based) → semantic clustering via `nvidia/llama-nemotron-embed-vl-1b-v2` → builds the Intermediate Representation (IR).
*   **Flow B**: The prompt embedding is compared against the 10 archetype blueprints in an in-memory Faiss index. The top 2 above 0.60 similarity supply the architectural rules; otherwise it falls back to General SaaS.
*   **Startup Pre-Warming**: Utilizes a FastAPI `lifespan` context manager to pre-warm the cloud embedder and Faiss vector index on boot, eliminating cold start delays.

### Phase 2 — Architect Agent
The **Principal Architect Agent** receives the full IR + rules and generates a `GeneratedArchitectureSpec` Pydantic object enforced by `instructor.Mode.JSON`:
- A normalized database schema, generated in chunks so large table sets stay within the token budget
- A REST API surface with auth strategy per endpoint
- Production-grade tech stack, DevOps config, resilience spec, and SpiceLayer

**Model**: `nvidia/nemotron-3-ultra-550b-a55b` via NVIDIA NIM (`LLM_MODEL` in `app/services/agents/generation.py`)  
**Parameters**: `max_tokens` sized per call — `1024` for project meta, `8192` for table chunks, `16384` for the full spec — with `temperature = 1.00`, `top_p = 1.00`  
**Timeout**: 360s (6 minutes) — real generation, no mock fallback

### Phase 3 — Review Panel (concurrent)
Four agents run simultaneously against the Architect's draft, all on `LLM_REVIEW_MODEL`:

| Agent | Model | Checks |
|---|---|---|
| DBA Agent | `nemotron-3-ultra-550b` | Schema normalization, foreign keys, tenant isolation |
| Security Agent | `nemotron-3-ultra-550b` | Unprotected write endpoints, auth coverage |
| PM Agent | `nemotron-3-ultra-550b` | Spec completeness vs. user requirements |
| Anti-Fragility Agent | `nemotron-3-ultra-550b` | Chaos scenarios, resilience rating, hardening checklist |

The panel has a 120-second budget. If it times out, the spec is kept and a fallback resilience report is attached. If a reviewer flags problems, one revision pass runs: schema issues redraft the whole spec, while security or PM issues regenerate only what was flagged.

A full generation, all phases included, took roughly 3.5 to 9 minutes on NVIDIA's free tier in November 2026.

---

# 💬 SAGE Chatbot

SAGE stands for **Specification Answering & Guidance Engine**.

It is a spec-aware AI assistant that:
- Loads the latest generated spec as system context.
- **Smart Context Pruning**: Strips out verbose DevOps Dockerfiles and Resilience scenario logs unless explicitly asked in the query, cutting context payload size by **70%**.
- Sends the last 5 exchanges as conversation memory (stored in the `chat_messages` table), and reloads the full history when the page opens.
- Classifies each question as `technical` (gets the full spec) or `business` (gets a short summary) before answering.

**Model**: `nvidia/nemotron-3-ultra-550b-a55b` (`LLM_SAGE_MODEL`)

---

# ⚙️ Tech Stack

| Technology | Purpose |
|---|---|
| **Next.js 16** (App Router) | Frontend framework with SSR and client components |
| **TypeScript** | Type-safe frontend development |
| **FastAPI** | Async Python REST API backend |
| **Pydantic + instructor** | Structured LLM output enforcement with JSON Mode parsing |
| **SQLAlchemy** | ORM for all database models |
| **Supabase (PgBouncer)** | Pooler URLs on port `5432` are automatically switched to transaction pooler port `6543` for safe concurrent scaling |
| **NVIDIA NIM API** | LLM inference — `nvidia/nemotron-3-ultra-550b-a55b` shared by the Architect, the four review agents, and SAGE Chat |
| **Faiss** | Vector similarity search for RAG blueprint retrieval |
| **CloudEmbedder** | Cloud-native RAG embedding via `nvidia/llama-nemotron-embed-vl-1b-v2` (0.75s latency) |
| **GLiNER** (optional) | Zero-shot NLP entity extraction; falls back to LLM and rule-based extraction when not installed |

---

# 🧠 Engineering Decisions

## Why `instructor` + Pydantic for structured output?
Forcing LLM output into a strongly-typed Pydantic schema (`GeneratedArchitectureSpec`) removes all post-processing and hallucination cleanup. Every field — tables, columns, endpoints, business rules, chaos scenarios — is type-validated before it reaches the frontend.

## Why NVIDIA NIM?
NVIDIA NIM serves large open-weight models behind an OpenAI-compatible API with high throughput, so the same client code works across models and switching model is a one-constant change.

## Why one shared model instead of a tiered 8B/20B/70B split?
It started as a tiered design — a large model for the Architect and `meta/llama-3.1-8b-instruct` for the cheap, short, structured review checks. **NVIDIA NIM deprecated that 8B model on 2026-08-26; it now returns `HTTP 410 Gone` and is not callable at all.** Rather than re-tier onto another small model that could be deprecated the same way, the Architect, the four review agents, entity extraction, and SAGE were consolidated onto a single endpoint:

```python
LLM_MODEL        = "nvidia/nemotron-3-ultra-550b-a55b"   # Architect
LLM_REVIEW_MODEL = "nvidia/nemotron-3-ultra-550b-a55b"   # DBA, Security, PM, Anti-Fragility, entity extraction
LLM_SAGE_MODEL   = "nvidia/nemotron-3-ultra-550b-a55b"   # SAGE chatbot
```

In November 2026 `openai/gpt-oss-20b`, the model these constants pointed at, stopped answering on NVIDIA's shared endpoint within 240 seconds, so all three moved to `nvidia/nemotron-3-ultra-550b-a55b`. It gave the most detailed answer among the fast models when the 57 chat models NVIDIA listed were compared on one short prompt, so treat that as a snapshot. Full generations on the free tier took roughly 3.5 to 9 minutes.

One consequence is worth calling out, because it is not a latency problem and looks like one: **these models emit hidden chain-of-thought before their JSON answer.** Every call site therefore budgets `max_tokens` well above the values that were tuned for the 8B — a tight budget raises `IncompleteOutputException` rather than simply responding slowly.

## Why PgBouncer in Production?
Holding one PostgreSQL connection per worker under serverless or high-concurrency scaling risks exhausting connection limits. Any `*.pooler.supabase.com:5432` URL is switched to PgBouncer's Transaction Pooler (port 6543) with explicit connection pools (`pool_size=5`, `max_overflow=10`). Direct `db.*.supabase.co` URLs are left as they are.

---

# 📂 Project Structure

```bash
.
├── backend/
│   ├── requirements.txt
│   ├── .env.example
│   ├── db/schema.sql              # Full Supabase schema
│   ├── app/
│   │   ├── main.py                    # FastAPI app entry — all routers registered
│   │   ├── api/
│   │   │   └── endpoints/
│   │   │       ├── generate.py        # POST /api/generate, GET /api/status/{id}
│   │   │       ├── chat.py            # POST /api/chat, GET /api/chat/history (SAGE)
│   │   │       └── dashboard_api.py   # Projects, specs, POST /pipelines/run (used by the UI), zip download, share links, plans
│   │   ├── core/
│   │   │   ├── auth.py                # Supabase token verification
│   │   │   └── db.py                  # SQLAlchemy engine + session factory (PgBouncer enabled)
│   │   ├── models/
│   │   │   └── spec_db.py             # All SQLAlchemy table models
│   │   ├── schemas/
│   │   │   └── spec.py                # Pydantic schemas (GeneratedArchitectureSpec etc.)
│   │   └── services/
│   │       ├── scaffold.py            # Turns a spec into a runnable NestJS/FastAPI project
│   │       ├── generation_service.py  # Pipeline orchestrator (NLP → Swarm → DB save)
│   │       ├── agents/
│   │       │   └── generation.py      # Architect, DBA, Security, PM, Anti-Fragility agents
│   │       ├── nlp/
│   │       │   ├── pipeline.py        # Flow A + Flow B parallel NLP runner
│   │       │   ├── router.py          # Semantic intent router (NvidiaEmbeddingEncoder)
│   │       │   ├── entity_extractor.py # GLiNER + LLM entity extraction
│   │       │   ├── clustering.py      # Semantic synonym clustering
│   │       │   └── implication_map.py # Integration implication rules
│   │       └── rag/
│   │           ├── retriever.py       # Faiss RAG blueprint retriever
│   │           └── blueprints.py      # 10 curated system archetype blueprints
│   └── test_api.py                    # End-to-end backend test harness
│
└── frontend/
    └── src/
        ├── app/
        │   ├── app/
        │   │   ├── dashboard/         # Main generation workspace
        │   │   ├── chatbot/           # SAGE chat interface
        │   │   ├── projects/          # Saved projects history
        │   │   ├── pipelines/         # Saved conversations history
        │   │   └── settings/          # User settings and profile
        │   ├── auth/                  # Supabase auth pages
        │   └── components/
        │       └── app-shell.tsx      # Shared navigation sidebar
        └── lib/
            ├── supabase-browser.ts    # Supabase browser client
            └── pricing-plans.ts       # Plans list with character & projects limits
```

---

# 🗄 Database Schema

[`backend/db/schema.sql`](backend/db/schema.sql) is the source of truth. The backend also runs SQLAlchemy `create_all` on startup, but that only adds missing tables, with looser column types and no foreign keys, so run `schema.sql` first.

## `workspaces`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| name | text | Workspace name |
| owner_id | uuid | Owner, nullable |
| created_at / updated_at | timestamptz | Timestamps |

## `projects`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| workspace_id | uuid | FK → workspaces, nullable |
| name | text | Display name, unique per user (case-insensitive) |
| description | text | Optional description |
| user_id | uuid | FK → auth.users |
| created_at / updated_at | timestamptz | Timestamps |

## `specs`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| project_id | uuid | FK → projects (cascade delete) |
| title | text | Spec display title |
| content | text | Raw user-provided spec text |
| source_type | text | Defaults to `paste` |
| user_id | uuid | FK → auth.users |
| created_at / updated_at | timestamptz | Timestamps |

## `pipeline_runs`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| project_id | uuid | FK → projects (cascade delete) |
| spec_id | uuid | FK → specs, nullable |
| status | text | Run status, e.g. `completed` |
| stages | jsonb | Stage metadata |
| result | jsonb | Output shown in the UI: entities, endpoints, rules, `code_skeleton`, `migration_sql`, `devops` |
| completed_at | timestamptz | Completion timestamp |
| user_id | uuid | FK → auth.users |

## `chat_messages`
| Column | Type | Description |
|---|---|---|
| id | varchar(36) | Primary key |
| spec_id | varchar(36) | Spec the conversation is about |
| user_id | varchar(36) | Supabase auth user ID |
| query | text | User's question |
| response | text | SAGE's response |
| intent | varchar(50) | `technical` or `business` |
| created_at | timestamp | Message timestamp |

## `profiles`
| Column | Type | Description |
|---|---|---|
| id | uuid | FK → auth.users |
| email | text | User email |
| username | text | Unique display username |
| full_name | text | Full name |
| avatar_url | text | Storage path for the avatar |
| plan_code | text | FK → pricing_plans.code, defaults to `starter` |

## `user_preferences`
| Column | Type | Description |
|---|---|---|
| user_id | uuid | Primary key, FK → auth.users |
| role / intent / experience | text | Onboarding answers |
| heard_about | text | `linkedin`, `product_hunt`, `google` or `other` |
| heard_about_other | text | Free-text answer, nullable |
| created_at | timestamptz | Timestamp |

## `pricing_plans`
| Column | Type | Description |
|---|---|---|
| id | uuid | Primary key |
| code | text | Unique plan identifier |
| display_name | text | Human-readable plan name |
| price_usd | integer | Price in whole US dollars (0 for free and custom plans) |
| monthly_project_limit | integer | Displayed project limit |
| monthly_run_limit | integer | Displayed run limit |
| is_active | boolean | Plan availability flag |

---

# 🚀 Local Setup

## Prerequisites
- Node.js 18+
- Python 3.12 (the version tested)
- A [Supabase](https://supabase.com) project
- An [NVIDIA NIM API key](https://build.nvidia.com) (free tier available)

---

## 1️⃣ Clone
```bash
git clone https://github.com/Kushal-Raj-G-S/Baxel-Spec-to-Backend-Architect.git
cd Baxel-Spec-to-Backend-Architect
```

---

## 2️⃣ Backend Setup
```bash
cd backend

# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate

# Mac/Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create environment file
cp .env.example .env
# Fill in your keys (see Environment Variables below)

# Start the server
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

---

### Database
Run [`backend/db/schema.sql`](backend/db/schema.sql) once in the Supabase SQL editor, before starting the backend. It creates every table, the plan rows, the private `avatars` bucket and row-level security.

### Authentication
In the Supabase dashboard, enable the sign-in methods you want (email/password, email OTP, Google, GitHub) and add `http://localhost:3000/auth/callback` to the redirect URLs.

`gliner` is optional and left out of `requirements.txt` because it pulls in PyTorch (about 2 GB). Without it, entity extraction falls back to rule-based and LLM extraction.

---

## 3️⃣ Frontend Setup
```bash
cd frontend

npm install

# Create environment file
cp .env.example .env.local
# Fill in your keys (see Environment Variables below)

npm run dev
```

Frontend runs at **http://localhost:3000**  
Backend API at **http://localhost:8000**

---

# 🔐 Environment Variables

## Backend — `backend/.env`
```env
# Supabase (a new-style sb_publishable_ key also goes in SUPABASE_ANON_KEY)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your_anon_key
SUPABASE_DB_URL=postgresql://postgres.your-project:password@your-region.pooler.supabase.com:6543/postgres

# NVIDIA NIM (LLM API)
NVIDIA_API_KEY=nvapi-xxxxxxxxxxxxxxxxxxxx
LLM_BASE_URL=https://integrate.api.nvidia.com/v1

# Models configuration (optional)
# Only LLM_REVIEW_MODEL is read from the environment (app/api/endpoints/chat.py);
# it defaults to the value in generation.py, so leave it unset unless overriding.
# Do NOT set meta/llama-3.1-8b-instruct here — NVIDIA NIM deprecated it on
# 2026-08-26 and it now returns HTTP 410 Gone.
# LLM_REVIEW_MODEL=nvidia/nemotron-3-ultra-550b-a55b

# Set to false only for local testing: every request becomes a fixed dev user
AUTH_ENABLED=true
```

## Frontend — `frontend/.env.local`
```env
NEXT_PUBLIC_SUPABASE_URL=https://your-project.supabase.co
NEXT_PUBLIC_SUPABASE_ANON_KEY=your_anon_key
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000
# Optional checkout links: NEXT_PUBLIC_BILLING_FREE_URL, _PRO_URL, _TEAM_URL, _ENTERPRISE_URL
```

---

# 🧪 Testing

## Backend API E2E test
```bash
cd backend
python test_api.py
```
This starts the API, submits a spec to `POST /api/generate`, polls `GET /api/status/{id}` for up to 15 minutes, and prints the generated tables. It sends no login token, so set `AUTH_ENABLED=false` in `backend/.env` while running it.

---

# ⚠️ Known Limitations

- **Generation is slow on the free tier.** A full run took roughly 3.5 to 9 minutes in November 2026, depending on NVIDIA's load and the size of the spec.
- **The intent check is keyword-based.** `semantic-router` loads, but its index is not synced, so routing falls back to keywords. Forcing the index on rejected valid specs in testing.
- **Scaffolds are a starting point.** Business actions (payments, refunds, status changes) return `501`.
- **Login needs an account table.** Auth is generated only for tables with a `password_hash` column. If a spec has none, its guarded routes can't be reached until you add one.
- **Ownership filtering is limited.** Rows are filtered to the caller only when the table has a foreign key to the account table.
- **Not yet tested:** scaffold Docker builds, avatar upload, and Google/GitHub sign-in.
- **CORS is open.** `app/main.py` uses `allow_origins=["*"]`. Restrict it before deploying.

---

# 📜 License
MIT License

---

<div align="center">

### Built with multi-agent AI, product obsession, and a healthy distrust of mock data.

</div>
