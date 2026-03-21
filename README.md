# Baxel - Spec-to-Backend Architect

Monorepo for a spec-to-backend MVP.

## Structure
- frontend: Next.js App Router + Tailwind UI
- backend: FastAPI service with AI pipeline stubs and Supabase-ready auth

## Prerequisites
- Node.js 18+
- Python 3.10+

## Frontend
```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env.local` from `frontend/.env.example`.

## Backend
```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Create `backend/.env` from `backend/.env.example`.

## Notes
- Replace in-memory stores with Supabase once ready.
- Wire Groq API key to enable real LLM calls.
