from __future__ import annotations

import json
import logging
import re
import ast
from typing import Any, Dict, List, Tuple

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)


ENTITY_CATALOG: List[Tuple[str, List[Dict[str, Any]], List[str]]] = [
    (
        "User",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "email", "type": "text", "constraints": ["not_null", "unique"]},
            {"name": "role", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        ["user", "buyer", "seller", "admin", "auth"],
    ),
    (
        "Product",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "seller_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "title", "type": "text", "constraints": ["not_null"]},
            {"name": "price", "type": "numeric", "constraints": ["not_null"]},
            {"name": "stock", "type": "integer", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        ["product", "catalog", "inventory"],
    ),
    (
        "Order",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "buyer_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "total_amount", "type": "numeric", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        ["order", "checkout"],
    ),
    (
        "Payment",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "order_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        ["payment", "invoice", "billing", "refund"],
    ),
]


def summarize_spec(content: str) -> dict:
    return {
        "summary": content[:220] + ("..." if len(content) > 220 else "")
    }


def _default_fields_for_entity(name: str) -> List[Dict[str, Any]]:
    key = name.lower().replace("_", "")
    presets: Dict[str, List[Dict[str, Any]]] = {
        "user": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "email", "type": "text", "constraints": ["not_null", "unique"]},
            {"name": "full_name", "type": "text", "constraints": ["not_null"]},
            {"name": "role", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        "organizer": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "company_name", "type": "text", "constraints": ["not_null"]},
            {"name": "contact_email", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        "event": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "organizer_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "venue_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "title", "type": "text", "constraints": ["not_null"]},
            {"name": "start_time", "type": "timestamptz", "constraints": ["not_null"]},
            {"name": "end_time", "type": "timestamptz", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
        "venue": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "name", "type": "text", "constraints": ["not_null"]},
            {"name": "address", "type": "text", "constraints": ["not_null"]},
            {"name": "capacity", "type": "integer", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        "tickettier": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "event_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "tier_name", "type": "text", "constraints": ["not_null"]},
            {"name": "price", "type": "numeric", "constraints": ["not_null"]},
            {"name": "quantity", "type": "integer", "constraints": ["not_null"]},
        ],
        "ticket": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "event_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "ticket_tier_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "qr_code", "type": "text", "constraints": ["not_null", "unique"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
        "attendance": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "event_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "checked_in_at", "type": "timestamptz", "constraints": []},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
        "waitlist": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "event_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "position", "type": "integer", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    }

    if key in presets:
        return presets[key]

    return [
        {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
        {"name": "name", "type": "text", "constraints": ["not_null"]},
        {"name": "status", "type": "text", "constraints": []},
        {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
    ]


def _ensure_spec_required_entities(content: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    text = content.lower()
    existing = {str(entity.get("name", "")).lower() for entity in entities}

    if "waitlist" in text and "waitlist" not in existing:
        entities.append({"name": "Waitlist", "fields": _default_fields_for_entity("Waitlist")})

    return entities


def _ensure_entity_field_depth(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for entity in entities:
        name = str(entity.get("name", "")).strip()
        fields = entity.get("fields", []) if isinstance(entity.get("fields"), list) else []
        normalized_fields: List[Dict[str, Any]] = []
        for field in fields:
            normalized = _normalize_field(field)
            if normalized:
                normalized_fields.append(normalized)

        if len(normalized_fields) < 3:
            normalized_fields = _default_fields_for_entity(name)

        result.append({"name": name, "fields": normalized_fields[:20]})
    return result


def _normalize_rule(rule: Any) -> Dict[str, str] | str | None:
    if isinstance(rule, dict):
        name = str(rule.get("name", "")).strip()
        rule_type = str(rule.get("type", "")).strip()
        trigger = str(rule.get("trigger_condition") or rule.get("trigger") or rule.get("condition") or "").strip()
        if not name and not trigger:
            return None
        return {
            "name": name or trigger,
            "type": rule_type,
            "trigger_condition": trigger,
        }

    text = str(rule).strip()
    if not text:
        return None
    return text


def _expected_min_entity_count(spec: str) -> int:
    return max(3, len(spec.split(".")) // 2)


# Fix ISSUE 3: normalize mixed constraint types to strict string[] schema.
def _normalize_constraints(value: Any) -> List[str]:
    valid_prefix = "check:"
    if isinstance(value, list):
        raw_items = [str(item).strip().lower() for item in value if str(item).strip()]
    elif isinstance(value, str):
        raw_items = [item.strip().lower() for item in value.split(",") if item.strip()]
    else:
        raw_items = []

    normalized: List[str] = []
    for item in raw_items:
        mapped = item.replace(" ", "_")
        if mapped in {
            "primary_key",
            "foreign_key",
            "not_null",
            "unique",
            "default_false",
            "default_true",
        } or mapped.startswith(valid_prefix):
            normalized.append(mapped)
    return normalized


def _normalize_field(field: Any) -> Dict[str, Any] | None:
    if isinstance(field, dict):
        name = str(field.get("name", "")).strip()
        field_type = str(field.get("type", "")).strip() or "text"
        constraints = _normalize_constraints(field.get("constraints", []))
        if not name:
            return None
        return {"name": name[:64], "type": field_type[:48], "constraints": constraints[:8]}

    if isinstance(field, str):
        parts = [part.strip() for part in field.split(" ") if part.strip()]
        if not parts:
            return None
        name = parts[0]
        inferred_type = parts[1] if len(parts) > 1 else "text"
        constraints = []
        lowered = field.lower()
        if "primary key" in lowered or " pk" in lowered:
            constraints.append("primary_key")
        if "foreign key" in lowered or " references " in lowered:
            constraints.append("foreign_key")
        if "not null" in lowered:
            constraints.append("not_null")
        if "unique" in lowered:
            constraints.append("unique")
        return {"name": name[:64], "type": inferred_type[:48], "constraints": constraints[:8]}

    return None


def _dedupe_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    seen = set()
    deduped: List[Dict[str, Any]] = []
    for entity in entities:
        name = str(entity.get("name", "")).strip()
        if not name:
            continue
        fields = entity.get("fields", [])
        fields_list = []
        if isinstance(fields, list):
            for field in fields:
                normalized = _normalize_field(field)
                if normalized:
                    fields_list.append(normalized)
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"name": name, "fields": fields_list})
    return deduped


def _dedupe_endpoints(endpoints: List[Dict[str, str]]) -> List[Dict[str, str]]:
    seen = set()
    deduped: List[Dict[str, str]] = []
    for endpoint in endpoints:
        method = str(endpoint.get("method", "")).upper().strip()
        path = str(endpoint.get("path", "")).strip()
        desc = str(endpoint.get("desc", "")).strip()
        errors_val = endpoint.get("errors", [])
        errors = [
            str(error).strip().lower().replace(" ", "_")
            for error in errors_val
            if str(error).strip()
        ] if isinstance(errors_val, list) else []
        if not method or not path.startswith("/"):
            continue
        key = (method, path)
        if key in seen:
            continue
        seen.add(key)
        deduped.append({"method": method, "path": path, "desc": desc, "errors": errors})
    return deduped


def _dedupe_rules(rules: List[Any]) -> List[Any]:
    seen = set()
    deduped: List[Any] = []
    for rule in rules:
        normalized = _normalize_rule(rule)
        if normalized is None:
            continue

        if isinstance(normalized, dict):
            key = json.dumps(normalized, sort_keys=True)
        else:
            key = normalized.lower()

        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _dedupe_strings(values: List[str]) -> List[str]:
    seen = set()
    deduped: List[str] = []
    for value in values:
        cleaned = str(value).strip()
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _build_blueprint_fallback(content: str) -> Dict:
    text = content.lower()

    entities: List[Dict] = []
    for name, fields, keywords in ENTITY_CATALOG:
        if any(keyword in text for keyword in keywords):
            entities.append({"name": name, "fields": fields})

    if not entities:
        entities = [
            {
                "name": "Project",
                "fields": [
                    {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
                    {"name": "name", "type": "text", "constraints": ["not_null"]},
                    {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
                ],
            },
            {
                "name": "Spec",
                "fields": [
                    {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
                    {"name": "project_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                    {"name": "content", "type": "text", "constraints": ["not_null"]},
                    {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
                ],
            },
        ]

    endpoints: List[Dict[str, str]] = []
    if any(e["name"] == "Product" for e in entities):
        endpoints.extend(
            [
                {"method": "GET", "path": "/products", "desc": "List products"},
                {"method": "POST", "path": "/products", "desc": "Create product"},
                {"method": "PATCH", "path": "/products/{id}", "desc": "Update product"},
                {"method": "DELETE", "path": "/products/{id}", "desc": "Archive product"},
            ]
        )
    if any(e["name"] == "Cart" for e in entities):
        endpoints.extend(
            [
                {"method": "GET", "path": "/cart", "desc": "Get active cart"},
                {"method": "POST", "path": "/cart/items", "desc": "Add item to cart"},
            ]
        )
    if any(e["name"] == "Order" for e in entities):
        endpoints.extend(
            [
                {"method": "POST", "path": "/orders", "desc": "Create order from cart"},
                {"method": "GET", "path": "/orders", "desc": "List orders"},
                {"method": "GET", "path": "/orders/{id}", "desc": "Get order by id"},
                {"method": "PATCH", "path": "/orders/{id}", "desc": "Update order status"},
            ]
        )
    if any(e["name"] == "Payment" for e in entities):
        endpoints.append({"method": "POST", "path": "/payments", "desc": "Capture or record payment"})
    if any(e["name"] == "Review" for e in entities):
        endpoints.append({"method": "POST", "path": "/reviews", "desc": "Submit delivered-order review"})
    if any(e["name"] == "Appointment" for e in entities):
        endpoints.extend(
            [
                {"method": "POST", "path": "/appointments", "desc": "Book appointment"},
                {"method": "GET", "path": "/appointments", "desc": "List appointments"},
            ]
        )

    if not endpoints:
        endpoints = [
            {"method": "POST", "path": "/projects", "desc": "Create a project"},
            {"method": "POST", "path": "/specs", "desc": "Upload a spec"},
            {"method": "POST", "path": "/pipelines/run", "desc": "Run pipeline"},
        ]

    rules: List[str] = ["Every entity needs a primary key and timestamps"]
    if any(role in text for role in ["buyer", "seller", "admin", "patient", "doctor"]):
        rules.append("Access control is role-scoped and tenant-safe")
    if "review" in text:
        rules.append("Reviews are allowed only after successful or delivered orders")
    if "stock" in text or "inventory" in text:
        rules.append("Order creation must validate stock availability")
    if "refund" in text or "payment" in text:
        rules.append("Payment state transitions are audited and idempotent")
    if "audit" in text:
        rules.append("Admin actions must be written to audit logs")

    relationships: List[str] = []
    entity_names = {item.get("name") for item in entities}
    if "User" in entity_names and "Order" in entity_names:
        relationships.append("User 1..* Order")
    if "Order" in entity_names and "OrderItem" in entity_names:
        relationships.append("Order 1..* OrderItem")
    if "Product" in entity_names and "OrderItem" in entity_names:
        relationships.append("Product 1..* OrderItem")
    if "Cart" in entity_names and "CartItem" in entity_names:
        relationships.append("Cart 1..* CartItem")
    if "Product" in entity_names and "Review" in entity_names:
        relationships.append("Product 1..* Review")

    join_tables: List[Dict[str, Any]] = []
    if "label" in text and "task" in text:
        join_tables.append(
            {
                "name": "task_labels",
                "left_entity": "Task",
                "right_entity": "Label",
                "purpose": "Many-to-many task labeling",
                "fields": [
                    "task_id uuid not null references tasks(id)",
                    "label_id uuid not null references labels(id)",
                    "created_at timestamptz not null default now()",
                    "primary key (task_id, label_id)",
                ],
            }
        )
    if "workspace" in text and "user" in text:
        join_tables.append(
            {
                "name": "workspace_users",
                "left_entity": "Workspace",
                "right_entity": "User",
                "purpose": "User membership and role in workspace",
                "fields": [
                    "workspace_id uuid not null references workspaces(id)",
                    "user_id uuid not null references users(id)",
                    "role text not null",
                    "created_at timestamptz not null default now()",
                    "primary key (workspace_id, user_id)",
                ],
            }
        )
    if "driver" in text and "vehicle" in text:
        join_tables.append(
            {
                "name": "driver_vehicles",
                "left_entity": "Driver",
                "right_entity": "Vehicle",
                "purpose": "Driver to vehicle assignments",
                "fields": [
                    "driver_id uuid not null references drivers(id)",
                    "vehicle_id uuid not null references vehicles(id)",
                    "active boolean not null default true",
                    "assigned_at timestamptz not null default now()",
                    "primary key (driver_id, vehicle_id)",
                ],
            }
        )

    default_errors = ["400 BAD_REQUEST", "401 UNAUTHORIZED", "403 FORBIDDEN", "404 NOT_FOUND", "409 CONFLICT", "422 VALIDATION_ERROR", "500 INTERNAL_SERVER_ERROR"]
    endpoints = [
        {
            "method": endpoint["method"],
            "path": endpoint["path"],
            "desc": endpoint["desc"],
            "errors": default_errors,
        }
        for endpoint in endpoints
    ]

    code_skeleton = {
        "models": "# SQLAlchemy-style models\nclass BaseModel: ...\n# entities generated from spec",
        "routers": "# FastAPI routers\n# CRUD + list/search endpoints with auth and pagination",
        "services": "# Domain services\n# validation, state transitions, and transaction boundaries",
    }

    migration_sql = (
        "-- Auto-generated migration skeleton\n"
        "create table if not exists projects (\n"
        "  id uuid primary key default gen_random_uuid(),\n"
        "  name text not null,\n"
        "  created_at timestamptz not null default now(),\n"
        "  updated_at timestamptz not null default now()\n"
        ");\n"
        "-- Add domain tables from entities and relationship foreign keys."
    )

    entities = _dedupe_entities(entities)
    endpoints = _dedupe_endpoints(endpoints)
    rules = _dedupe_rules(rules)
    relationships = _dedupe_strings(relationships)

    return {
        "summary": summarize_spec(content),
        "entities": entities,
        "endpoints": endpoints,
        "rules": rules,
        "relationships": relationships,
        "join_tables": join_tables,
        "code_skeleton": code_skeleton,
        "migration_sql": migration_sql,
    }


def _extract_json(text: str) -> Dict[str, Any]:
    stripped = text.strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        pass

    match = re.search(r"\{[\s\S]*\}", stripped)
    if not match:
        raise ValueError("No JSON object found in model output")
    return json.loads(match.group(0))


def _call_groq_chat(messages: List[Dict[str, str]], model: str, timeout: int = 45) -> Dict[str, Any]:
    logger.info("[GROQ] request.start model=%s timeout=%s", model, timeout)
    response = httpx.post(
        "https://api.groq.com/openai/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "temperature": 0.2,
            "messages": messages,
            "response_format": {"type": "json_object"},
        },
        timeout=timeout,
    )
    response.raise_for_status()
    payload = response.json()
    content_text = payload["choices"][0]["message"]["content"]
    logger.info("[GROQ] request.end model=%s", model)
    return _extract_json(content_text)


def _generate_relationships_and_join_tables(
    content: str,
    entities: List[Dict[str, Any]],
    model: str,
) -> Dict[str, Any]:
    prompt = (
        "Return JSON with keys relationships and join_tables. "
        "relationships: array of strings like 'Parent 1..* Child'. "
        "join_tables: array of {name,left_entity,right_entity,purpose,fields}. "
        "Infer from the spec and entities only."
        f"\n\nSPEC:\n{content}\n\nENTITIES:\n{json.dumps([e.get('name') for e in entities])}"
    )

    try:
        raw = _call_groq_chat(
            [
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": prompt},
            ],
            model=model,
        )
    except Exception as error:
        logger.error("[RELATIONSHIPS] Failed: %s", error)
        return {"relationships": [], "join_tables": []}

    relationships_raw = raw.get("relationships") if isinstance(raw.get("relationships"), list) else []
    join_tables_raw = raw.get("join_tables") if isinstance(raw.get("join_tables"), list) else []

    relationships = _dedupe_strings([str(item).strip() for item in relationships_raw if str(item).strip()])

    join_tables: List[Dict[str, Any]] = []
    for item in join_tables_raw[:24]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        if not name:
            continue
        left_entity = str(item.get("left_entity", "")).strip()
        right_entity = str(item.get("right_entity", "")).strip()
        purpose = str(item.get("purpose", "")).strip()
        fields_val = item.get("fields", [])
        fields = [str(field).strip()[:160] for field in fields_val if str(field).strip()] if isinstance(fields_val, list) else []
        join_tables.append(
            {
                "name": name[:80],
                "left_entity": left_entity[:60],
                "right_entity": right_entity[:60],
                "purpose": purpose[:180],
                "fields": fields[:20],
            }
        )

    return {"relationships": relationships, "join_tables": join_tables}


# Fix ISSUE 5, ISSUE 6, ISSUE 7: enforce PATCH semantics, rule-derived snake_case errors, and nested 1..* endpoints.
def _generate_api_surface(content: str, entities: List[Dict[str, Any]], relationships: List[str], rules: List[str], model: str) -> List[Dict[str, Any]]:
    prompt = (
        "Generate API endpoints as JSON: { endpoints: [{method,path,desc,errors}] }. "
        "Use PATCH (not PUT) when only partial fields are updated. "
        "Use PATCH /resource/{id}/status for state transitions. "
        "For each 1..* relationship, include GET /parent/{id}/children nested endpoint. "
        "For each endpoint, include domain-specific snake_case errors derived from business rules. "
        "Errors must be codes like student_already_enrolled, driver_not_verified, insufficient_stock. "
        f"\n\nSPEC:\n{content}\n\nENTITIES:\n{json.dumps(entities)}\n\nRELATIONSHIPS:\n{json.dumps(relationships)}\n\nBUSINESS_RULES:\n{json.dumps(rules)}"
    )
    raw = _call_groq_chat(
        [
            {"role": "system", "content": "Return only JSON."},
            {"role": "user", "content": prompt},
        ],
        model=model,
    )
    endpoints_raw = raw.get("endpoints") if isinstance(raw.get("endpoints"), list) else []
    sanitized: List[Dict[str, Any]] = []
    for item in endpoints_raw:
        if not isinstance(item, dict):
            continue
        method = str(item.get("method", "")).upper().strip()
        path = str(item.get("path", "")).strip()
        desc = str(item.get("desc", "")).strip()
        errors = item.get("errors", [])
        if method and path.startswith("/"):
            sanitized.append({"method": method, "path": path, "desc": desc, "errors": errors})
    return _dedupe_endpoints(sanitized)


# Fix ISSUE 1: force code skeleton parity across models/routers/services.
def _generate_code_skeleton(entities: List[Dict[str, Any]], model: str) -> Dict[str, str]:
    names = [str(entity.get("name", "")).strip() for entity in entities if str(entity.get("name", "")).strip()]
    logger.info("[SKELETON] Received %s entities for skeleton generation", len(names))

    def _to_entries(value: Any) -> List[str]:
        if isinstance(value, list):
            result: List[str] = []
            for item in value:
                if isinstance(item, dict):
                    label = str(item.get("name") or item.get("entity") or "").strip()
                    details = str(item.get("details") or item.get("purpose") or "").strip()
                    if label:
                        result.append(f"- {label}: {details}" if details else f"- {label}")
                else:
                    text = str(item).strip()
                    if text:
                        result.append(f"- {text}")
            return result
        text = str(value or "").strip()
        if not text:
            return []
        return [line.strip() for line in text.splitlines() if line.strip()]

    warning = ""
    models_entries: List[str] = []
    routers_entries: List[str] = []
    services_entries: List[str] = []

    for _attempt in range(2):
        prompt = (
            "Return JSON with keys models, routers, services as arrays. "
            f"You MUST generate exactly {len(names)} entries in models, {len(names)} entries in routers, and {len(names)} entries in services. "
            "You MUST generate one router and one service entry for EVERY entity listed in the models section. "
            f"Entity list: {json.dumps(names)}. "
            f"{warning}"
        )
        raw = _call_groq_chat(
            [
                {"role": "system", "content": "Return only JSON."},
                {"role": "user", "content": prompt},
            ],
            model=model,
        )

        models_entries = _to_entries(raw.get("models"))
        routers_entries = _to_entries(raw.get("routers"))
        services_entries = _to_entries(raw.get("services"))

        if len(models_entries) == len(names) and len(routers_entries) == len(names) and len(services_entries) == len(names):
            break

        warning = (
            f"Your previous response had {len(models_entries)} models, {len(routers_entries)} routers, and "
            f"{len(services_entries)} services but I gave you {len(names)} entities. Generate the missing ones now."
        )

    return {
        "models": "\n".join(models_entries),
        "routers": "\n".join(routers_entries),
        "services": "\n".join(services_entries),
    }


# Fix ISSUE 2: generate migration SQL in entity batches with CREATE TABLE count validation/retry.
def _generate_migration_sql_batched(entities: List[Dict[str, Any]], relationships: List[str], model: str) -> str:
    entity_names = [str(entity.get("name", "")).strip() for entity in entities if str(entity.get("name", "")).strip()]
    if not entity_names:
        return ""

    sql_chunks: List[str] = []

    def _normalize_sql_chunk(value: Any) -> str:
        if isinstance(value, list):
            return "\n\n".join(_normalize_sql_chunk(item) for item in value if _normalize_sql_chunk(item).strip())

        if isinstance(value, str):
            text = value.strip()
            if not text:
                return ""

            # Try parsing JSON-encoded arrays first.
            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return _normalize_sql_chunk(parsed)
            except Exception:
                pass

            # Handle python-list-like strings from model output.
            if text.startswith("[") and text.endswith("]"):
                try:
                    parsed_literal = ast.literal_eval(text)
                    if isinstance(parsed_literal, list):
                        return _normalize_sql_chunk(parsed_literal)
                except Exception:
                    pass

            return text

        return str(value).strip()

    for start in range(0, len(entity_names), 5):
        batch = entity_names[start : start + 5]
        expected = len(batch)
        warning = ""

        for attempt in range(2):
            prompt = (
                "Return JSON with key migration_sql only. "
                "Generate CREATE TABLE for ALL entities listed. Do not stop early. "
                f"If there are N entities, there must be exactly N CREATE TABLE statements. N={expected}. "
                f"Entities: {json.dumps(batch)}. Relationships context: {json.dumps(relationships)}. "
                "Use postgres syntax, include PK/FK/UNIQUE/CHECK where relevant. "
                f"{warning}"
            )
            raw = _call_groq_chat(
                [
                    {"role": "system", "content": "Return only JSON."},
                    {"role": "user", "content": prompt},
                ],
                model=model,
                timeout=60,
            )
            migration_sql = _normalize_sql_chunk(raw.get("migration_sql", ""))
            create_count = len(re.findall(r"create\s+table", migration_sql, flags=re.IGNORECASE))
            if create_count == expected:
                sql_chunks.append(migration_sql)
                break
            warning = (
                f"WARNING: previous output had {create_count} CREATE TABLE statements; expected {expected}. "
                "Regenerate complete SQL now."
            )
        else:
            continue

    return "\n\n".join(chunk for chunk in sql_chunks if chunk)


def _sanitize_blueprint(raw: Dict[str, Any], content: str) -> Dict[str, Any]:
    entities_raw = raw.get("entities") if isinstance(raw.get("entities"), list) else []
    endpoints_raw = raw.get("endpoints") if isinstance(raw.get("endpoints"), list) else []
    rules_raw = raw.get("rules") if isinstance(raw.get("rules"), list) else []
    relationships_raw = raw.get("relationships") if isinstance(raw.get("relationships"), list) else []
    join_tables_raw = raw.get("join_tables") if isinstance(raw.get("join_tables"), list) else []
    code_skeleton_raw = raw.get("code_skeleton") if isinstance(raw.get("code_skeleton"), dict) else {}
    migration_sql_raw = raw.get("migration_sql")
    summary_raw = raw.get("summary")

    entities: List[Dict[str, Any]] = []
    for item in entities_raw[:120]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        fields_val = item.get("fields", [])
        fields: List[Dict[str, Any]] = []
        if isinstance(fields_val, list):
            for field in fields_val:
                normalized = _normalize_field(field)
                if normalized:
                    fields.append(normalized)
        if name:
            entities.append({"name": name[:60], "fields": fields[:16]})

    endpoints: List[Dict[str, str]] = []
    for item in endpoints_raw[:240]:
        if not isinstance(item, dict):
            continue
        method = str(item.get("method", "")).upper().strip()
        path = str(item.get("path", "")).strip()
        desc = str(item.get("desc", "")).strip()
        errors_val = item.get("errors", [])
        errors = [str(error).strip()[:80] for error in errors_val if str(error).strip()] if isinstance(errors_val, list) else []
        if method and path.startswith("/"):
            endpoints.append({"method": method[:10], "path": path[:120], "desc": desc[:140], "errors": errors[:8]})

    rules = [rule for rule in rules_raw[:160]]
    relationships = [str(item).strip()[:140] for item in relationships_raw[:300] if str(item).strip()]

    join_tables: List[Dict[str, Any]] = []
    for item in join_tables_raw[:120]:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name", "")).strip()
        left_entity = str(item.get("left_entity", "")).strip()
        right_entity = str(item.get("right_entity", "")).strip()
        purpose = str(item.get("purpose", "")).strip()
        fields_val = item.get("fields", [])
        fields = [str(field).strip()[:140] for field in fields_val if str(field).strip()] if isinstance(fields_val, list) else []
        if name:
            join_tables.append(
                {
                    "name": name[:80],
                    "left_entity": left_entity[:60],
                    "right_entity": right_entity[:60],
                    "purpose": purpose[:180],
                    "fields": fields[:12],
                }
            )

    code_skeleton = {
        "models": str(code_skeleton_raw.get("models", "")).strip()[:2400],
        "routers": str(code_skeleton_raw.get("routers", "")).strip()[:2400],
        "services": str(code_skeleton_raw.get("services", "")).strip()[:2400],
    }
    migration_sql = str(migration_sql_raw or "").strip()[:6000]

    summary_text = ""
    if isinstance(summary_raw, str):
        summary_text = summary_raw.strip()
    elif isinstance(summary_raw, dict):
        summary_text = str(summary_raw.get("summary", "")).strip()

    if not summary_text:
        summary_text = summarize_spec(content)["summary"]

    entities = _dedupe_entities(entities)
    entities = _ensure_entity_field_depth(entities)
    endpoints = _dedupe_endpoints(endpoints)
    rules = _dedupe_rules(rules)
    relationships = _dedupe_strings(relationships)

    if not entities:
        return _build_blueprint_fallback(content)

    return {
        "summary": {"summary": summary_text[:320]},
        "entities": entities,
        "endpoints": endpoints,
        "rules": rules,
        "relationships": relationships,
        "join_tables": join_tables,
        "code_skeleton": code_skeleton,
        "migration_sql": migration_sql,
    }


def _call_groq_for_blueprint(content: str, model: str) -> Dict[str, Any]:
    if not settings.groq_api_key:
        raise ValueError("GROQ_API_KEY is not configured")

    # Fix ISSUE 3: strict entity-field JSON schema instruction with constraints as string[] only.
    system_prompt = (
        "You are a senior backend architect. Return only valid JSON with keys: "
        "summary (string), entities, relationships, join_tables, rules. "
        "Each field MUST follow this exact JSON format: {'name': string, 'type': string, 'constraints': string[]}. "
        "The constraints field is ALWAYS an array of strings, never a plain string. "
        "For every entity, include practical domain fields (not only id). Prefer 4-8 fields per entity including business attributes and keys. "
        "Valid constraint values: primary_key, foreign_key, not_null, unique, default_false, default_true, check:<expression>."
    )

    user_prompt = (
        "Generate a backend blueprint from this product spec. "
        "Include domain-specific entities, relationships, join tables, and business rules.\n\n"
        f"SPEC:\n{content}"
    )
    return _call_groq_chat(
        [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        model=model,
    )


def build_blueprint(content: str) -> Dict:
    logger.info("[PIPELINE] blueprint.start content_chars=%s", len(content or ""))
    model_candidates: List[str] = []
    if settings.groq_model:
        model_candidates.append(settings.groq_model)
    if settings.groq_fallback_model and settings.groq_fallback_model not in model_candidates:
        model_candidates.append(settings.groq_fallback_model)

    for model in model_candidates:
        try:
            expected_min_count = _expected_min_entity_count(content)
            warning = ""
            blueprint = None
            attempt_count = 0
            enrichment_state = {
                "relationships": "skipped",
                "api_surface": "skipped",
                "code_skeleton": "skipped",
                "migration_sql": "skipped",
            }

            for attempt in range(3):
                attempt_count = attempt + 1
                logger.info("[PIPELINE] blueprint.attempt model=%s attempt=%s", model, attempt_count)
                raw = _call_groq_for_blueprint(content if not warning else f"{content}\n\n{warning}", model=model)
                candidate = _sanitize_blueprint(raw, content)
                entities = candidate.get("entities", [])
                logger.info("[DEBUG] Entity count: %s", len(entities))

                if len(entities) >= expected_min_count:
                    blueprint = candidate
                    break

                if attempt < 2:
                    warning = (
                        "IMPORTANT: The previous response was incomplete. "
                        f"The spec mentions at least {expected_min_count} distinct entities. "
                        "List ALL of them now. Do not stop early."
                    )
                else:
                    blueprint = candidate

            if blueprint is None:
                continue

            entities = blueprint.get("entities", [])
            entities = _ensure_spec_required_entities(content, entities)
            entities = _ensure_entity_field_depth(entities)
            blueprint["entities"] = entities
            relationships = blueprint.get("relationships", [])
            rules = blueprint.get("rules", [])

            rel_output = _generate_relationships_and_join_tables(content, entities, model=model)
            blueprint["relationships"] = rel_output.get("relationships", [])
            blueprint["join_tables"] = rel_output.get("join_tables", [])
            relationships = blueprint.get("relationships", [])
            enrichment_state["relationships"] = "groq"

            try:
                blueprint["endpoints"] = _generate_api_surface(content, entities, relationships, rules, model=model)
                enrichment_state["api_surface"] = "groq"
            except Exception:
                enrichment_state["api_surface"] = "fallback-existing"

            try:
                blueprint["code_skeleton"] = _generate_code_skeleton(entities, model=model)
                enrichment_state["code_skeleton"] = "groq"
            except Exception:
                enrichment_state["code_skeleton"] = "fallback-existing"

            try:
                migration_sql = _generate_migration_sql_batched(entities, relationships, model=model)
                if migration_sql:
                    blueprint["migration_sql"] = migration_sql
                    enrichment_state["migration_sql"] = "groq"
                else:
                    enrichment_state["migration_sql"] = "fallback-existing"
            except Exception:
                enrichment_state["migration_sql"] = "fallback-existing"

            blueprint["__meta"] = {
                "source": "groq",
                "provider": "groq",
                "model": model,
                "attempts": attempt_count,
                "content_chars": len(content or ""),
                "enrichments": enrichment_state,
            }

            logger.info(
                "[PIPELINE] blueprint.success source=groq model=%s attempts=%s entities=%s endpoints=%s rules=%s",
                model,
                attempt_count,
                len(blueprint.get("entities") or []),
                len(blueprint.get("endpoints") or []),
                len(blueprint.get("rules") or []),
            )

            return blueprint
        except Exception as error:
            logger.warning("[PIPELINE] blueprint.model_failed model=%s error=%s", model, error)
            continue

    fallback = _build_blueprint_fallback(content)
    fallback["__meta"] = {
        "source": "fallback",
        "provider": "baxel-local",
        "model": None,
        "attempts": 0,
        "content_chars": len(content or ""),
        "enrichments": {
            "relationships": "fallback",
            "api_surface": "fallback",
            "code_skeleton": "fallback",
            "migration_sql": "fallback",
        },
    }
    logger.warning(
        "[PIPELINE] blueprint.fallback_used entities=%s endpoints=%s rules=%s",
        len(fallback.get("entities") or []),
        len(fallback.get("endpoints") or []),
        len(fallback.get("rules") or []),
    )
    return fallback
