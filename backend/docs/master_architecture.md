# Baxel Master Architecture: The MVP Pipeline

This document serves as the master blueprint connecting the four pillars of the Baxel AI Backend. It outlines how a raw user prompt flows through the system, gets processed by specialized NLP models, enriched by Architectural RAG, orchestrated by AI agents, and finally compiled into a flawless, "Spicy" JSON output.

This pipeline is designed to be highly modular, allowing LLM models to be swapped out instantly without breaking the core logic.

---

## 🏗️ Phase 1: High-Speed Input Processing (The "Brain")
*Goal: Normalize the messy prompt and drastically reduce the cognitive burden on the LLM.*

1. **Semantic Routing (`semantic-router`)**: 
   - The user prompt hits the FastAPI endpoint. A fast vector check confirms if the prompt is valid; spam is rejected in milliseconds.
2. **Concurrency Block (`asyncio.gather`)**:
   To minimize response times, the backend kicks off two independent asynchronous flows concurrently:
   - **Flow A (Entity Processing Pipeline)**:
     - **Zero-Shot NER (`GLiNER`)**: Dynamically extracts raw nouns and actors from the prompt.
     - **Semantic Clustering (`BGE-M3` + `Faiss`)**: Maps entities into high-dimensional space to cluster synonyms (e.g., merging "Admin" and "Superuser").
   - **Flow B (Architectural Retrieval Pipeline)**:
     - **Archetype Classification**: Classifies the prompt's archetype.
     - **Vector DB Query**: Queries the vector database for matching blueprints.
3. **The Handoff**: 
   - Once both concurrent flows complete, the backend combines the structured entities and retrieved blueprints to compile the Intermediate Representation (IR).

---

## 🧠 Phase 2: Context Engineering (Architectural RAG)
*Goal: Inject Principal Engineer knowledge into the context window to prevent junior-level hallucination.*

1. **Archetype Classification & Caching**:
   - The Semantic Router categorizes the project type (e.g., Video Streaming, E-commerce, B2B SaaS). To prevent cache-incoherency across multiple containerized Docker worker processes, caching is stored in **Redis** (as configured in `TechStack`). The system falls back to a local in-memory LRU cache only in single-process development environments.
2. **Vector DB Query**:
   - The backend queries our highly specialized Vector Database containing **Elite System Design Blueprints** (e.g., AWS Well-Architected frameworks) utilizing a strict relevance threshold (`min_similarity_score=0.6`) and falling back to a "General SaaS" template if needed.
3. **Constraint Injection**:
   - The system retrieves strict architectural rules (e.g., *"Must use a message broker for async tasks"*) and injects them alongside the clean IR from Phase 1.

---

## 🤖 Phase 3: Agentic Output Generation (The "Engineering Team")
*Goal: Generate the architecture using specialized roles and self-healing mechanisms.*

Instead of a single LLM call, the prompt (IR + RAG constraints) enters a Multi-Agent Swarm (powered by a framework like LangGraph):

1. **The Principal Architect Agent**: 
   - Drafts the initial database schema and API routes based on the hard constraints.
2. **The Review Panel (with Debate Caps & Timeouts)**:
   - **DBA Agent**: Scans the draft for missing foreign keys or bad indexing.
   - **Security Agent**: Rejects the draft if destructive endpoints lack authentication.
   - **Debate Loop Escape Hatch**: To prevent infinite revision loops, we enforce a strict `max_review_cycles=2` cap on the debate cycle between the Architect and Review Agents. If unresolved, the draft moves to Stage 3 with warning metadata.
   - **Per-Agent Timeout**: Each agent execution is bounded by a hard timeout (e.g., 10 seconds in LangGraph) to prevent hung requests.
3. **The Self-Healing Compiler (`Instructor`)**:
   - The approved draft is cast against our strict Pydantic schemas. 
   - If a required field is missing, Pydantic throws a `ValidationError`. The backend catches this, passes the stack trace back to the LLM, and forces a fix until the JSON is mathematically flawless (up to 3 retries max before outputting a degraded partial spec).

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
After the spec is generated, the UI presents a chatbot. To protect the LLM context window limits, the backend runs the user query through a lightweight LLM classifier to decide whether to inject the full JSON spec (for technical queries like "Will this scale?") or a lightweight summary (for general queries). Specs are persisted in a database schema supporting versioning (`parent_spec_id`, `version`) to enable seamless regeneration workflows (e.g. changing Postgres to MongoDB).
