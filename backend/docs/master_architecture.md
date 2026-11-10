# Baxel Master Architecture: The MVP Pipeline

This document serves as the master blueprint connecting the four pillars of the Baxel AI Backend. It outlines how a raw user prompt flows through the system, gets processed by specialized NLP models, enriched by Architectural RAG, orchestrated by AI agents, and finally compiled into a flawless, "Spicy" JSON output.

This pipeline is designed to be highly modular, allowing LLM models to be swapped out instantly without breaking the core logic.

---

## 🏗️ Phase 1: High-Speed Input Processing (The "Brain")
*Goal: Normalize the messy prompt and drastically reduce the cognitive burden on the LLM.*

1. **Intent Check**:
   - The user prompt hits the FastAPI endpoint and an intent check rejects anything that isn't a software spec. A keyword check makes this call today: `semantic-router` loads, but its index is not synced.
2. **Concurrency Block (`asyncio.gather`)**:
   To minimize response times, the backend kicks off two independent asynchronous flows concurrently:
   - **Flow A (Entity Processing Pipeline)**:
     - **Zero-Shot NER (`GLiNER`, optional)**: Dynamically extracts raw nouns and actors from the prompt. Without it, LLM and rule-based extraction are used.
     - **Semantic Clustering (`nvidia/llama-nemotron-embed-vl-1b-v2` + `Faiss`)**: Maps entities into high-dimensional space to cluster synonyms (e.g., merging "Admin" and "Superuser").
   - **Flow B (Architectural Retrieval Pipeline)**:
     - **Archetype Retrieval**: Embeds the prompt and finds the closest blueprints in an in-memory Faiss index.
3. **The Handoff**:
   - Once both concurrent flows complete, the backend combines the structured entities and retrieved blueprints to compile the Intermediate Representation (IR).

---

## 🧠 Phase 2: Context Engineering (Architectural RAG)
*Goal: Inject Principal Engineer knowledge into the context window to prevent junior-level hallucination.*

1. **Blueprint Retrieval**:
   - The backend compares the prompt embedding against 10 curated **System Design Blueprints** held in an in-memory Faiss index, taking the top 2 (`top_k=2`) above a relevance threshold (`min_similarity_score=0.6`) and falling back to a "General SaaS" blueprint if none qualify. Retrieval is not cached.
2. **Constraint Injection**:
   - The system retrieves strict architectural rules (e.g., *"Must use a message broker for async tasks"*) and injects them alongside the clean IR from Phase 1.

---

## 🤖 Phase 3: Agentic Output Generation (The "Engineering Team")
*Goal: Generate the architecture using specialized roles and self-healing mechanisms.*

Instead of a single LLM call, the prompt (IR + RAG constraints) enters a Multi-Agent Swarm, orchestrated with plain `asyncio` calls:

1. **The Principal Architect Agent**:
   - Drafts the initial database schema and API routes based on the hard constraints.
2. **The Review Panel (concurrent)**:
   - **DBA Agent**: Scans the draft for missing foreign keys or bad indexing.
   - **Security Agent**: Flags destructive endpoints that lack authentication.
   - **PM Agent**: Checks the draft covers the original requirements.
   - **Anti-Fragility Agent**: Produces chaos scenarios and a hardening checklist.
   - **One Revision Pass**: If reviewers flag issues, one revision runs. Schema issues redraft the whole spec; security or PM issues regenerate only what was flagged.
   - **Timeout**: The panel shares a 120-second budget. If it runs out, the spec is kept and a fallback resilience report is attached.
3. **The Self-Healing Compiler (`Instructor`)**:
   - The approved draft is cast against our strict Pydantic schemas.
   - If a required field is missing, Pydantic throws a `ValidationError`. The backend catches this, passes the stack trace back to the LLM, and forces a fix, with up to 3 retries depending on the call.

---

## 🌶️ Phase 4: The Final Output Spec (The "Sweet Spot + Spice")
*Goal: Deliver a perfect JSON payload to the Next.js frontend that is highly useful but emotionally engaging.*

The final compiled JSON (defined in `backend/app/schemas/spec.py`) contains:
1. **Metadata & Tech Stack**: Includes the exact prompt used (for the Chatbot feature) and the language/framework chosen.
2. **Core Fundamentals**: Clean Entity-Relationship tables and fully mapped REST API endpoints.
3. **DevOps Setup**: Required `.env` variables and a ready-to-run `Dockerfile`.
4. **The Spice Layer**:
   - **Devil's Advocate**: A playful warning about potential bottlenecks.
   - **Design Rationale**: Explanations for why specific architectural choices were made.
   - **Time Saved Metric**: A psychological hook displaying hours of boilerplate writing saved.

---

## 🔄 The Bonus Layer: "Chat with your Architecture"
After the spec is generated, the UI presents a chatbot. To protect the LLM context window limits, the backend runs the user query through a lightweight LLM classifier to decide whether to inject the full JSON spec (for technical queries like "Will this scale?") or a lightweight summary (for general queries). The spec metadata records `version` and `parent_spec_id` so a later run can be traced to the spec it iterated from.
