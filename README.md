# Baxel

Spec-to-backend system for turning raw product ideas into structured backend output: schema, API, rules, SQL, and implementation scaffolds.

## Why This Project Exists

Most AI coding tools start after architecture is already decided.
Baxel focuses on the stage before coding: translating messy product intent into backend structure that teams can review, iterate, and ship.

## Core Product Behavior

- Accepts product specs from the dashboard
- Expands and normalizes the spec internally
- Produces backend artifacts:
	- entities and relationships
	- endpoint surface
	- business rules
	- migration SQL
	- code skeleton sections
- Applies plan-aware output visibility and usage limits
- Supports shareable run links

## Monorepo Layout

- frontend: Next.js App Router UI
- backend: FastAPI service and orchestration
- backend/migrations: Supabase/Postgres SQL migrations

## Stack

- Frontend: Next.js, React, Tailwind CSS
- Backend: FastAPI, Pydantic
- Data/Auth/Storage: Supabase
- Generation orchestration: backend service pipeline

## Local Setup

### 1) Frontend

```bash
cd frontend
npm install
npm run dev
```

Create frontend/.env.local from frontend/.env.example and set NEXT_PUBLIC_API_BASE_URL.

### 2) Backend

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create backend/.env from backend/.env.example.

## Required Environment Variables

Frontend:

- NEXT_PUBLIC_API_BASE_URL
- NEXT_PUBLIC_BILLING_STARTER_URL
- NEXT_PUBLIC_BILLING_CREATOR_URL
- NEXT_PUBLIC_BILLING_STUDIO_URL
- NEXT_PUBLIC_BILLING_GROWTH_URL
- NEXT_PUBLIC_BILLING_ENTERPRISE_URL

Backend (common):

- SUPABASE_URL
- SUPABASE_SERVICE_ROLE_KEY
- SUPABASE_JWT_SECRET
- AUTH_ENABLED
- LOG_LEVEL
- GROQ_API_KEY (if using live model provider flow)

## Database Migrations

Apply SQL files in backend/migrations sequentially.
At minimum, run all existing migrations in numeric order in your Supabase SQL editor.

## Plan Model

Supported plan codes:

- starter
- creator
- studio
- growth
- enterprise

Limits are enforced server-side, and generation routes return HTTP 402 when the current plan cannot proceed.

## API Surface

- /projects
- /specs
- /pipelines
- /dashboard
- /profile
- /runs

## Developer Notes

- The frontend now avoids showing a fake Starter label during initial plan fetch.
- Plan display is cache-assisted on client side for better perceived speed.
- Locked preview messaging is intentionally starter-only.

## Troubleshooting

- 402 responses:
	- check profile plan payload
	- check monthly run/project counters
	- verify plan override and subscription state
- Avatar upload issues:
	- ensure avatars storage bucket exists
	- verify Supabase policies

## Resume Value

Baxel demonstrates full-stack ownership with real product constraints:

- multi-tenant auth and profile management
- plan-driven feature gating
- AI pipeline orchestration with structured outputs
- practical UX work around trust, latency, and fallback states
