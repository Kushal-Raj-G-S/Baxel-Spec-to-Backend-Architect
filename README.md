<div align="center">
  <img src="frontend/public/logo.png" width="80" alt="Baxel Logo" />
  <h1 align="center">Baxel</h1>
  <p align="center">
    <strong>From messy product specs to production-ready backend architecture in minutes.</strong>
  </p>
  <p align="center">
    Stop writing boilerplate. Start building features.
  </p>
</div>

---

## 🚀 Overview

Baxel is an intelligent **Spec-to-Backend** system. Most AI coding tools start *after* architecture is already decided. Baxel focuses on the stage *before* coding: translating unstructured product intent into a structured backend blueprint that teams can review, iterate, and ship immediately.

## ✨ Key Features

- **🧠 Spec Intelligence:** Multi-agent reasoning pipeline that normalizes language, extracts actors, and defines constraints from raw text.
- **🏗️ Visual Architecture:** Automatically generates an Entity-Relationship blueprint with relationship hints and data types.
- **🔌 API Generator:** Drafts REST & OpenAPI endpoints complete with request payloads, response shapes, and error contracts.
- **📜 Business Rules:** Surfaces invariants and compliance checks, highlighting conflicts or missing logic as actionable checklists.
- **📦 Code Export:** Pushes generated, production-ready FastAPI or Node.js boilerplates with migrations, routing, and database integrations.
- **🎨 Premium UX:** A stunning, modern dark-olive theme featuring smooth scroll-driven animations (Scrollytelling) and dynamic user experiences.

## 🛠️ Tech Stack

### Frontend
- **Framework:** Next.js (App Router), React
- **Styling:** Tailwind CSS, Framer Motion (for fluid animations)
- **Deployment:** Vercel (recommended)

### Backend
- **Framework:** FastAPI, Pydantic
- **Database & Auth:** Supabase (PostgreSQL)
- **AI/Orchestration:** Backend service pipeline (Groq / specialized LLM providers)

## 💻 Local Setup

### 1) Frontend

```bash
cd frontend
npm install
npm run dev
```

> **Note:** Create `frontend/.env.local` from `frontend/.env.example` and set `NEXT_PUBLIC_API_BASE_URL`.

### 2) Backend

```bash
cd backend
python -m venv .venv
# Activate virtual environment
# Windows: .venv\Scripts\activate
# Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

> **Note:** Create `backend/.env` from `backend/.env.example`.

## ⚙️ Required Environment Variables

**Frontend:**
- `NEXT_PUBLIC_API_BASE_URL`
- `NEXT_PUBLIC_BILLING_STARTER_URL` ... and other plan URLs.

**Backend (common):**
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_JWT_SECRET`
- `AUTH_ENABLED`
- `LOG_LEVEL`
- `GROQ_API_KEY` (if using live model provider flow)

## 🗄️ Database Migrations

Apply SQL files in `backend/migrations` sequentially. At minimum, run all existing migrations in numeric order in your Supabase SQL editor to set up the necessary tables and policies.

## 💎 Pricing & Plan Model

Supported plan codes: `starter`, `creator`, `studio`, `growth`, `enterprise`.
Limits are enforced server-side, and generation routes will gracefully return HTTP 402 when the current plan's limits are reached.

## 📈 Resume Value

Baxel demonstrates full-stack ownership with real product constraints:
- Multi-tenant auth and profile management
- Plan-driven feature gating and quota enforcement
- AI pipeline orchestration with structured outputs
- Premium frontend aesthetics with high-performance animations and dark-mode elegance
- Practical UX work around trust, latency, and fallback states

---

<div align="center">
  <p>Built with ❤️ for modern engineering teams.</p>
</div>
