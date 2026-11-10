# 🔮 Baxel Future Features & Enhancements

This document outlines high-value features planned for subsequent iteration cycles of the Baxel Spec-to-Backend Architect workspace.

---

## 1. 📝 Visual Click-to-Edit Database Schema
*   **Concept**: Make the generated Entity-Relationship schema diagram interactive instead of static/read-only.
*   **User Flow**: 
    1. A developer double-clicks a database column name or data type inside the entities panel to modify it directly.
    2. Toggles nullable flags or changes foreign key targets via dropdowns.
    3. The frontend immediately updates the React `result` state, dynamically recalculating the migration SQL and generated project files in real-time, bypassing any LLM round-trip costs.

## 2. 🔍 Generation Version Diff Tracker
*   **Concept**: View a visual Git-style diff highlighting the delta changes between the current run and previous iterations.
*   **User Flow**:
    1. The developer triggers a spec revision (e.g., adding billing).
    2. Instead of manually comparing the new 24 tables with the old 20 tables, a "Diff View" highlights new schemas/endpoints in green and deletions in red.
    3. Displays clear action logs: `[+] Added table subscriptions`, `[~] Modified column credit_limit (Decimal -> Integer)`.

## 3. 💬 SAGE Chat-to-Apply Action Cards
*   **Concept**: Enable the spec-aware SAGE Chatbot to modify the active specification design based on conversation agreement.
*   **User Flow**:
    1. During a technical conversation, SAGE suggests: *"I recommend adding a user_roles join table to support many-to-many role mappings."*
    2. SAGE renders an inline suggestion card button: **`[Apply Change to Spec]`**.
    3. Clicking the button updates the project spec state and updates the dashboard schema layout.
