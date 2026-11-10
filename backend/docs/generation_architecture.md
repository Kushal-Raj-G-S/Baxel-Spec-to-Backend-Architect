# The "Agentic Generation" Architecture

If the NLP pipeline is the "Brain" mapping out the rules, the Output Generation pipeline is the "Engineering Team" building the product.

To go truly "crazy" and pitch a highly advanced system, we cannot just make a single API call to an LLM and hope it gets a massive JSON schema right. We need **Multi-Agent Orchestration** and **Self-Healing Compilation**.

## The Old Way (Single Prompting)
- Send prompt to LLM -> LLM returns JSON -> Hope it parses. (High failure rate, highly generic).

## The Elite Way: Multi-Agent Debate & Compilation
We treat the generation process like a real tech company. Instead of one LLM acting alone, we spawn a micro-swarm of specialized LLM Agents, orchestrated with plain `asyncio` calls.

### Stage 1: The Draft (The Principal Architect)
- **Input:** The clean Intermediate Representation (IR) from our NLP pipeline + The constraints from Architectural RAG.
- **Action:** A high-reasoning model drafts the initial ERD and API routes.

### Stage 2: The Multi-Agent Review Panel (The "Wow" Factor)
Before the JSON is finalized, it is passed through four concurrent "Review Agents":
1. **The DBA Agent:** Checks the draft for missing foreign keys, circular dependencies, or missing pagination.
2. **The Security Agent:** Scans the endpoints. If a route deletes users but isn't flagged `is_protected = true`, it rejects the draft.
3. **The Product Manager Agent:** Checks if the draft actually fulfills the user's original business intent.
4. **The Anti-Fragility Agent:** Simulates failure scenarios and writes a hardening checklist.

*If any agent finds a flaw, the draft is sent back to the Architect for a rapid fix. To prevent vague feedback, each Review Agent must output a strict `ReviewResult` Pydantic model (`passed: bool`, `issues: List[str]`, `suggested_fixes: List[str]`). This guarantees the Architect knows exactly what to fix.*
- **One Revision Pass**: At most one revision runs. Schema issues redraft the whole spec; security or PM issues regenerate only what was flagged.
- **Timeout**: The review panel shares a 120-second budget. If it runs out, the spec is kept and a fallback resilience report is attached.

### Stage 3: The Strict Compiler (Self-Healing Outputs)
LLMs hallucinate JSON structures all the time. To prevent the frontend from crashing, we use **Self-Healing Compilation**.
- We use the `Instructor` Python library to cast the final draft into our `GeneratedArchitectureSpec` Pydantic model.
- **The Magic:** If the LLM misses a required field (e.g., `tech_stack.framework` is missing), Pydantic throws a `ValidationError`. The backend catches this error, automatically feeds the exact stack trace back to the LLM, and says *"You missed this field. Fix it."*
- The loop is capped per call (`max_retries` of 0 to 3 depending on the call), so cost is bounded. Prompts the intent check is unsure about are marked `generation_status: "partial"`.

### Stage 4: Async Processing Budget
A full run took roughly 3.5 to 9 minutes on NVIDIA's free tier in November 2026. The dashboard calls `POST /pipelines/run` and waits for the result, animating the stages on a timer. `POST /api/generate` is the background alternative: it returns a `spec_id` and `status: "processing"` immediately, and `GET /api/status/{id}` reports progress.

### Stage 5: The Scaffold
`app/services/scaffold.py` turns the spec into a downloadable NestJS or FastAPI project. It decides what each endpoint does from its route, generates auth and CRUD handlers where the meaning is clear, and leaves business actions as `501` stubs. Runs stored by older generator versions are rebuilt on download.

## Why This is Pitch-Perfect
- **Unbreakable UI:** Because of the Self-Healing Compiler, the Next.js frontend will *never* receive a malformed JSON payload. Zero frontend crashes.
- **Agentic Workflows:** Multi-Agent architectures are the current holy grail of AI development. Pitching a "Review Panel" of AI agents proves you are building next-generation workflows, not just ChatGPT wrappers.
- **Quality Assurance:** The Security and DBA review agents guarantee that the generated code isn't just syntax-correct, but actually safe for production.
