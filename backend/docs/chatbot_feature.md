# "Chat with your Architecture" Feature

This document outlines the "Chatbot" UX layer that sits on top of the generated architecture spec. 

## The Problem (The Persona Gap)
The core Baxel output (see `final_output_structure.md`) is designed specifically for **Developers**. It contains column types, HTTP methods, and Dockerfiles. 
However, Baxel's users also include **Founders and CEOs** who need to extract different value from the architecture, such as cost estimates, plain-English summaries, or business logic clarifications. If we bloated the core schema with all this information, it would overwhelm the developer persona.

## The Solution: Architecture Chatbot
Instead of forcing all personas into one static UI, we provide a conversational AI assistant directly next to the generated spec.

### How it Works (Backend Context Injection)
When a user opens the chat interface, the frontend sends a prompt to a new backend endpoint (e.g., `POST /api/chat`).
Crucially, the backend injects two pieces of massive context into the LLM's system prompt before sending the user's message:
1. **The Original User Prompt**: (Saved in `SpecMetadata.prompt_used`).
2. **The Generated JSON Spec**: To protect the LLM context window limits, the backend runs the user's message through a **lightweight intent classifier** (a fast, single-sentence LLM classification prompt checking if the query requires architecture-level details). 
   - *Technical queries* (e.g., "Will this scale to a million users?", "How are tables connected?", or generating ORM schemas) get the full JSON spec injected.
   - *General/business queries* (e.g., "Write a pitch for investors" or general billing/cost advice) only receive a lightweight summary of the tech stack and the original prompt anchor.

### Example Use Cases
Because the LLM has complete knowledge of the architecture, it acts as the Principal Architect answering questions about the design:

- **The CEO / Founder Queries:**
  - *"Write a summary of this architecture for my investors."*
  - *"How much will this cost to run on AWS for 10,000 users?"*
  - *"Does this architecture comply with GDPR?"*

- **The Developer Queries:**
  - *"Can you generate the React Query hooks for the user endpoints?"*
  - *"Write the Prisma schema for this database."*
  - *"How should I paginate the `List Invoices` endpoint?"*

## Implementation Plan
1. **Persistence Layer (with Versioning)**: Define a `specs` table in our database to support iterative regeneration.
   - Schema: `id (UUID)`, `user_id (UUID)`, `parent_spec_id (UUID, Nullable)`, `version (Integer)`, `prompt_used (Text)`, `generated_json (JSONB)`, `created_at (Timestamp)`.
   - By capturing `parent_spec_id` and `version`, we support workflows like *"regenerate the spec but use MongoDB instead of Postgres"*.
2. **New Schema**: Create a Pydantic schema for the Chat endpoint (`ChatRequest(message: str, spec_id: UUID)`).
2. **New Endpoint**: `POST /api/chat` that retrieves the saved spec from Supabase and orchestrates the LLM call.
3. **Frontend Integration**: A floating chat widget or a split-pane view next to the visual architecture blueprint.
