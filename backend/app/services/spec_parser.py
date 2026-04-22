from __future__ import annotations

import json
import logging
import re
import ast
from typing import Any, Dict, List, Optional, Set, Tuple

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
        "loan": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "borrower_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "lender_id", "type": "uuid", "constraints": ["foreign_key"]},
            {"name": "amount", "type": "numeric", "constraints": ["not_null", "check:amount>0"]},
            {"name": "interest_rate", "type": "numeric", "constraints": ["not_null", "check:interest_rate>=0"]},
            {"name": "risk_tier", "type": "text", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        "borrower": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "credit_score", "type": "integer", "constraints": ["not_null", "check:credit_score>=300"]},
            {"name": "income", "type": "numeric", "constraints": ["not_null"]},
            {"name": "requested_amount", "type": "numeric", "constraints": []},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        "lender": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "available_funds", "type": "numeric", "constraints": []},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        "repaymentschedule": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "loan_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "emi", "type": "numeric", "constraints": ["not_null"]},
            {"name": "tenure", "type": "integer", "constraints": ["not_null"]},
            {"name": "payment_frequency", "type": "text", "constraints": ["not_null"]},
        ],
        "payment": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "loan_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "installment_number", "type": "integer", "constraints": ["not_null"]},
            {"name": "payment_date", "type": "date", "constraints": []},
            {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
        ],
        "loanapplication": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "borrower_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        "kycdocument": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "document_type", "type": "text", "constraints": ["not_null"]},
            {"name": "document_url", "type": "text", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
        "notification": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "task_id", "type": "uuid", "constraints": ["foreign_key"]},
            {"name": "message", "type": "text", "constraints": ["not_null"]},
            {"name": "channel", "type": "text", "constraints": []},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
        "admin": [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "role", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
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


def _infer_entity_fields_from_spec(entity_name: str, content: str) -> List[Dict[str, Any]]:
    text = (content or "").lower()
    if not text:
        return []

    entity_snake = _to_snake_case(entity_name)
    tokens = {
        entity_name.lower(),
        entity_snake,
        _pluralize(entity_snake),
        entity_snake.replace("_", " "),
    }
    sentences = [segment.strip() for segment in re.split(r"[\n\.!?;]+", text) if segment.strip()]
    context = " ".join(sentence for sentence in sentences if any(token in sentence for token in tokens))
    has_entity_context = bool(context.strip())
    if not context:
        context = ""

    inferred: List[Dict[str, Any]] = []

    def add(name: str, field_type: str, constraints: Optional[List[str]] = None) -> None:
        inferred.append({"name": name, "type": field_type, "constraints": constraints or []})

    keyword_rules: List[Tuple[List[str], Dict[str, Any]]] = [
        (["email"], {"name": "email", "type": "text", "constraints": ["not_null", "unique"]}),
        (["description"], {"name": "description", "type": "text", "constraints": []}),
        (["title"], {"name": "title", "type": "text", "constraints": ["not_null"]}),
        (["slug"], {"name": "slug", "type": "text", "constraints": ["unique"]}),
        (["status"], {"name": "status", "type": "text", "constraints": []}),
        (["audit"], {"name": "action", "type": "text", "constraints": ["not_null"]}),
        (["analytics", "usage"], {"name": "metric_name", "type": "text", "constraints": ["not_null"]}),
        (["analytics", "usage"], {"name": "metric_value", "type": "numeric", "constraints": []}),
        (["analytics", "usage"], {"name": "measured_at", "type": "timestamptz", "constraints": ["not_null"]}),
        (["invite", "invitation"], {"name": "invited_at", "type": "timestamptz", "constraints": []}),
        (["permission"], {"name": "permissions", "type": "jsonb", "constraints": []}),
    ]

    for keywords, field in keyword_rules:
        if has_entity_context and any(keyword in context for keyword in keywords):
            add(field["name"], field["type"], field.get("constraints") or [])

    entity_key = _to_snake_case(entity_name)
    fk_owner_map: Dict[str, List[Tuple[List[str], str]]] = {
        "workspace": [(["organization"], "organization_id")],
        "member": [(["workspace"], "workspace_id"), (["user"], "user_id")],
        "role": [(["workspace"], "workspace_id")],
        "project": [(["workspace"], "workspace_id"), (["owner"], "owner_id")],
        "usage_analytics": [(["project"], "project_id")],
        "audit_log": [(["project"], "project_id"), (["actor", "member", "user"], "actor_id")],
        "feature": [(["tier"], "tier_id"), (["project"], "project_id")],
        "tier": [(["organization"], "organization_id")],
        "loan_application": [(["borrower"], "borrower_id"), (["admin"], "admin_id")],
        "repayment_schedule": [(["loan"], "loan_id")],
        "payment": [(["loan", "repayment"], "loan_id"), (["schedule"], "repayment_schedule_id")],
        "notification": [(["user"], "user_id"), (["task", "project", "review"], "task_id")],
        "kyc_document": [(["user"], "user_id")],
    }

    for keywords, field_name in fk_owner_map.get(entity_key, []):
        if not has_entity_context:
            continue
        if not any(keyword in context for keyword in keywords):
            continue
        if field_name == f"{entity_key}_id":
            continue
        add(field_name, "uuid", ["foreign_key"])

    return inferred


def _ensure_entity_field_depth(entities: List[Dict[str, Any]], content: str = "") -> List[Dict[str, Any]]:
    result: List[Dict[str, Any]] = []
    for entity in entities:
        name = str(entity.get("name", "")).strip()
        fields = entity.get("fields", []) if isinstance(entity.get("fields"), list) else []
        normalized_fields: List[Dict[str, Any]] = []
        for field in fields:
            normalized = _normalize_field(field)
            if normalized:
                normalized_fields.append(normalized)

        default_fields = _default_fields_for_entity(name)
        existing_names = {str(item.get("name", "")).lower() for item in normalized_fields}
        for default_field in default_fields:
            field_name = str(default_field.get("name", "")).lower()
            if field_name and field_name not in existing_names:
                normalized_fields.append(default_field)
                existing_names.add(field_name)

        inferred_fields = _infer_entity_fields_from_spec(name, content)
        for inferred in inferred_fields:
            field_name = str(inferred.get("name", "")).lower()
            if field_name and field_name not in existing_names:
                normalized_fields.append(inferred)
                existing_names.add(field_name)

        if len(normalized_fields) < 3:
            normalized_fields = default_fields

        result.append({"name": name, "fields": normalized_fields[:20]})
    return result


def _inject_fintech_domain_fields(content: str, entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    text = (content or "").lower()
    if not entities:
        return entities

    def _entity_by_name(target: str) -> Optional[Dict[str, Any]]:
        for entity in entities:
            if str(entity.get("name", "")).strip().lower() == target.lower():
                return entity
        return None

    loan = _entity_by_name("loan")
    if not loan:
        return entities

    fields = loan.get("fields") if isinstance(loan.get("fields"), list) else []
    existing = {str(field.get("name", "")).lower() for field in fields if isinstance(field, dict)}

    def _add(name: str, field_type: str, constraints: Optional[List[str]] = None) -> None:
        if name.lower() in existing:
            return
        fields.append({"name": name, "type": field_type, "constraints": constraints or []})
        existing.add(name.lower())

    if "missed payment" in text or "delinquen" in text:
        _add("missed_payments_count", "integer", ["not_null"])
    if "origination fee" in text or "origination" in text:
        _add("origination_fee", "numeric", [])
    if "disbursed" in text or "deduct from disbursement" in text:
        _add("disbursed_amount", "numeric", [])

    loan["fields"] = fields
    return entities


def _log_field_richness_warning(entities: List[Dict[str, Any]], content: str) -> None:
    if len(entities) < 4:
        return

    scaffold = {"id", "name", "status", "created_at"}
    thin_entities: List[str] = []
    normalized_signatures: Dict[str, List[str]] = {}

    for entity in entities:
        name = str(entity.get("name", "")).strip() or "<unknown>"
        fields = entity.get("fields") if isinstance(entity.get("fields"), list) else []
        field_names = [str(field.get("name", "")).strip().lower() for field in fields if isinstance(field, dict)]
        unique = sorted({field for field in field_names if field})

        if unique and set(unique).issubset(scaffold):
            thin_entities.append(name)

        signature = "|".join(unique)
        normalized_signatures.setdefault(signature, []).append(name)

    duplicated_groups = [group for group in normalized_signatures.values() if len(group) >= 3]
    if thin_entities or duplicated_groups:
        logger.warning(
            "[QUALITY] Low field richness detected thin_entities=%s duplicate_field_groups=%s content_chars=%s",
            thin_entities,
            duplicated_groups,
            len(content or ""),
        )


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


def _target_entity_range(content: str) -> tuple[int, int]:
    size = len(str(content or "").strip())
    if size <= 700:
        return (15, 30)
    if size <= 1800:
        return (25, 45)
    return (40, 60)


def _is_infrastructure_entity(name: str) -> bool:
    lowered = str(name or "").strip().lower()
    if not lowered:
        return True
    banned_exact = {
        "system", "platform", "tool", "pipeline", "queue", "worker", "server", "cluster",
        "kubernetes", "load_balancer", "monitoring", "logging", "infrastructure", "cloud",
        "devops", "telemetry", "observability",
    }
    banned_fragments = [
        "infra", "k8s", "kubernetes", "devops", "load balancer", "server", "queue", "broker",
        "cloud", "monitor", "log", "alert", "deploy", "ci", "cd",
    ]
    if lowered in banned_exact:
        return True
    return any(fragment in lowered for fragment in banned_fragments)


def _sanitize_structured_entities(content: str, entities_raw: Any) -> List[Dict[str, Any]]:
    entities: List[Dict[str, Any]] = []
    if not isinstance(entities_raw, list):
        return entities

    for item in entities_raw:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        purpose = str(item.get("purpose") or "").strip()
        relevance_raw = item.get("relevance_score")
        try:
            relevance = int(relevance_raw) if relevance_raw not in (None, "") else 5
        except Exception:
            relevance = 5

        if not name or _is_infrastructure_entity(name):
            continue
        if relevance < 3:
            continue
        if not purpose:
            continue

        entities.append(
            {
                "name": name[:64],
                "purpose": purpose[:260],
                "relevance_score": max(0, min(5, relevance)),
            }
        )

    seen = set()
    deduped: List[Dict[str, Any]] = []
    for entity in sorted(entities, key=lambda value: value.get("relevance_score", 0), reverse=True):
        key = str(entity.get("name", "")).strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entity)

    minimum, _maximum = _target_entity_range(content)
    if len(deduped) < minimum:
        logger.warning(
            "[PIPELINE] spec.expand.low_entity_count entities=%s target_min=%s",
            len(deduped),
            minimum,
        )
    return deduped


def trigger_simplification_pass(entities: List[Dict[str, Any]], target_count: int = 45) -> List[Dict[str, Any]]:
    # Merge over-fragmented entity variants by stripping low-value suffixes to a shared stem.
    low_value_suffixes = {
        "metadata",
        "meta",
        "state",
        "status",
        "config",
        "configuration",
        "settings",
        "context",
        "details",
        "detail",
        "info",
        "profile",
    }

    merged: Dict[str, Dict[str, Any]] = {}
    canonical_stem_map = {
        "execution": "workflow_run",
        "run": "workflow_run",
        "instance": "workflow_run",
        "context": "workflow_run",
        "execution_context": "workflow_run",
        "workflow_execution": "workflow_run",
        "workflow_instance": "workflow_run",
        "workflow_context": "workflow_run",
    }
    for entity in entities:
        name = str(entity.get("name") or "").strip()
        if not name:
            continue
        purpose = str(entity.get("purpose") or "").strip()
        score = int(entity.get("relevance_score") or 0)
        tokens = [token for token in re.split(r"[_\s-]+", name.lower()) if token]
        while len(tokens) > 1 and tokens[-1] in low_value_suffixes:
            tokens = tokens[:-1]
        stem = "_".join(tokens) or _to_snake_case(name)
        stem = canonical_stem_map.get(stem, stem)

        existing = merged.get(stem)
        if not existing:
            merged[stem] = {"name": name[:64], "purpose": purpose[:260], "relevance_score": score}
            continue

        existing_purpose = str(existing.get("purpose") or "")
        if len(purpose) > len(existing_purpose):
            existing["purpose"] = purpose[:260]
        existing["relevance_score"] = max(int(existing.get("relevance_score") or 0), score)

    simplified = sorted(merged.values(), key=lambda item: int(item.get("relevance_score") or 0), reverse=True)
    if len(simplified) > target_count:
        simplified = simplified[:target_count]
    return simplified


def _apply_entity_necessity_check(
    entities: List[Dict[str, Any]],
    relationships: List[str],
    workflows: List[Dict[str, Any]],
    content: str,
    plan_code: str | None = None,
) -> tuple[List[Dict[str, Any]], List[str]]:
    field_like_exact = {
        "state",
        "status",
        "type",
        "category",
        "condition",
        "configuration",
        "config",
        "metadata",
        "context",
        "response",
        "feedback",
        "constraint",
        "validationrule",
        "validation_rule",
        "rule",
        "setting",
        "settings",
    }
    field_like_suffixes = (
        "_status",
        "_state",
        "_type",
        "_config",
        "_configuration",
        "_metadata",
        "_context",
    )

    workflow_text = " ".join(
        [
            str(item.get("name") or "") + " " + " ".join(item.get("steps") or [])
            for item in workflows
            if isinstance(item, dict)
        ]
    ).lower()

    kept: List[Dict[str, Any]] = []
    converted_notes: List[str] = []
    for entity in entities:
        entity_name = str(entity.get("name") or "").strip()
        if not entity_name:
            continue
        key = _to_snake_case(entity_name)
        compact = key.replace("_", "")
        relation_count = sum(1 for rel in relationships if compact and compact in _to_snake_case(str(rel)))
        appears_in_workflow = bool(compact and compact in workflow_text.replace(" ", ""))

        needs_table = relation_count >= 2 or (relation_count >= 1 and appears_in_workflow)
        is_field_like = compact in {item.replace("_", "") for item in field_like_exact} or key.endswith(field_like_suffixes)

        if is_field_like and not needs_table:
            converted_notes.append(f"{entity_name} -> field/enum/json (no independent lifecycle/query needs)")
            continue

        kept.append(entity)

    if str(plan_code or "").strip().lower() == "enterprise":
        names = {_to_snake_case(str(item.get("name") or "")) for item in kept}
        authority_present = bool(names.intersection({"tenant", "organization", "workspace", "account"}))
        cues = ["tenant", "organization", "workspace", "multi-tenant", "company", "enterprise", "team"]
        if not authority_present and any(cue in str(content or "").lower() for cue in cues):
            kept.insert(
                0,
                {
                    "name": "Organization",
                    "purpose": "Core authority boundary for tenant-scoped users, workflows, and access control.",
                    "relevance_score": 5,
                },
            )
            converted_notes.append("Added Organization as core authority entity for tenant boundary")

    return kept, converted_notes[:40]


def _render_expansion_spec(content: str, payload: Dict[str, Any], plan_code: str | None = None) -> Dict[str, Any]:
    summary = str(payload.get("product_summary") or "").strip()

    roles_raw = payload.get("user_roles") if isinstance(payload.get("user_roles"), list) else []
    roles: List[Dict[str, Any]] = []
    for item in roles_raw[:10]:
        if not isinstance(item, dict):
            continue
        role_name = str(item.get("name") or "").strip()
        responsibilities_raw = item.get("responsibilities") if isinstance(item.get("responsibilities"), list) else []
        responsibilities = [str(value).strip() for value in responsibilities_raw if str(value).strip()]
        if role_name and responsibilities:
            roles.append({"name": role_name[:64], "responsibilities": responsibilities[:8]})

    workflows_raw = payload.get("core_workflows") if isinstance(payload.get("core_workflows"), list) else []
    if not workflows_raw and isinstance(payload.get("workflows"), list):
        workflows_raw = payload.get("workflows")
    workflows: List[Dict[str, Any]] = []
    for item in workflows_raw[:8]:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            steps_raw = item.get("steps") if isinstance(item.get("steps"), list) else []
            steps = [str(step).strip() for step in steps_raw if str(step).strip()]
            state_changes_raw = item.get("state_changes") if isinstance(item.get("state_changes"), list) else []
            state_changes = [str(change).strip() for change in state_changes_raw if str(change).strip()]
            if name and steps:
                workflows.append({"name": name[:90], "steps": steps[:10], "state_changes": state_changes[:8]})
            continue

        text = str(item).strip()
        if text:
            workflows.append({"name": text[:90], "steps": [text[:140]], "state_changes": []})

    entities_payload = payload.get("entities")
    if not isinstance(entities_payload, list):
        entities_payload = []
    if not entities_payload and isinstance(payload.get("final_entities"), list):
        entities_payload = [
            {
                "name": str(item.get("name") or "").strip(),
                "purpose": str(item.get("purpose") or "").strip(),
                "relevance_score": 5,
            }
            for item in payload.get("final_entities")
            if isinstance(item, dict)
        ]

    entities = _sanitize_structured_entities(content, entities_payload)
    if str(plan_code or "").strip().lower() == "enterprise" and len(entities) > 60:
        logger.warning("[PIPELINE] spec.expand.entity_overflow entities=%s action=simplification_pass", len(entities))
        entities = trigger_simplification_pass(entities, target_count=35)
    allowed_entity_names = {str(item.get("name", "")).lower() for item in entities}

    relationships_raw = payload.get("relationships") if isinstance(payload.get("relationships"), list) else []
    relationships: List[str] = []
    for rel in relationships_raw[:120]:
        text = str(rel).strip()
        if not text:
            continue
        text_lower = text.lower()
        if not any(entity_name in text_lower for entity_name in allowed_entity_names):
            continue
        relationships.append(text[:180])

    entities, necessity_conversions = _apply_entity_necessity_check(
        entities=entities,
        relationships=relationships,
        workflows=workflows,
        content=content,
        plan_code=plan_code,
    )
    if str(plan_code or "").strip().lower() == "enterprise" and len(entities) > 40:
        logger.warning("[PIPELINE] spec.expand.enterprise_cap_applied entities=%s max=%s", len(entities), 40)
        entities = trigger_simplification_pass(entities, target_count=35)
        if len(entities) > 40:
            entities = entities[:40]
    allowed_entity_names = {str(item.get("name", "")).lower() for item in entities}
    relationships = [
        rel for rel in relationships
        if any(entity_name in rel.lower() for entity_name in allowed_entity_names)
    ]

    business_rules_raw = payload.get("business_rules") if isinstance(payload.get("business_rules"), list) else []
    business_rules = [str(rule).strip()[:220] for rule in business_rules_raw if str(rule).strip()][:30]

    edge_cases_raw = payload.get("edge_cases") if isinstance(payload.get("edge_cases"), list) else []
    edge_cases = [str(case).strip()[:220] for case in edge_cases_raw if str(case).strip()][:20]

    inferred_items = [f"Entity inferred: {item.get('name')}" for item in entities[:20]]
    invalid_entities_removed = payload.get("invalid_entities_removed")
    if isinstance(invalid_entities_removed, list):
        inferred_items.extend(
            [
                f"Invalid entity removed: {str(item).strip()[:80]}"
                for item in invalid_entities_removed
                if str(item).strip()
            ][:20]
        )
    inferred_items.extend([f"Necessity check: {note}" for note in necessity_conversions])

    lines: List[str] = []
    lines.append("1. Product Summary")
    lines.append(summary or summarize_spec(content)["summary"])
    lines.append("")

    lines.append("2. User Roles (with responsibilities)")
    if roles:
        for role in roles:
            lines.append(f"- {role['name']}: " + "; ".join(role["responsibilities"]))
    else:
        lines.append("- Primary user: submits ideas and iterates backend outputs.")
    lines.append("")

    lines.append("3. Core Workflows (step-by-step)")
    if workflows:
        for index, workflow in enumerate(workflows[:6], start=1):
            lines.append(f"{index}. {workflow['name']}")
            for step in workflow["steps"]:
                lines.append(f"- {step}")
            if workflow.get("state_changes"):
                lines.append("- State changes: " + "; ".join(workflow["state_changes"]))
    else:
        lines.append("1. Idea submission and refinement")
        lines.append("- User submits an idea, reviews generated blueprint, and iterates")
        lines.append("- State changes: draft -> generated -> revised")
    lines.append("")

    lines.append("4. Entities")
    if entities:
        for entity in entities:
            lines.append(
                f"- {entity['name']}: purpose={entity['purpose']}; relevance_score={entity['relevance_score']}"
            )
    else:
        lines.append("- User: purpose=actor identity and access context; relevance_score=5")
        lines.append("- Project: purpose=container for product idea and outputs; relevance_score=5")
        lines.append("- Spec: purpose=product description used for generation; relevance_score=5")
    lines.append("")

    lines.append("5. Relationships (high-level)")
    if relationships:
        for relation in relationships[:80]:
            lines.append(f"- {relation}")
    else:
        lines.append("- User 1..* Project")
        lines.append("- Project 1..* Spec")
    lines.append("")

    lines.append("6. Key Business Rules")
    if business_rules:
        for rule in business_rules:
            lines.append(f"- {rule}")
    else:
        lines.append("- Every workflow must validate actor permissions before state changes")
    lines.append("")

    lines.append("7. Edge Cases")
    if edge_cases:
        for case in edge_cases:
            lines.append(f"- {case}")
    else:
        lines.append("- Duplicate submissions should be idempotent")
        lines.append("- Invalid transitions should return validation errors")

    return {
        "expanded_spec": "\n".join(lines).strip(),
        "inferred_items": inferred_items,
    }


def _heuristic_expand_spec(content: str, target_chars: int = 6000) -> Dict[str, Any]:
    base = str(content or "").strip()
    if not base:
        return {
            "expanded_spec": "",
            "inferred_items": [],
            "source": "heuristic",
        }

    summary = summarize_spec(base).get("summary")
    entities = [
        {"name": "User", "purpose": "primary actor identity and ownership context", "relevance_score": 5},
        {"name": "Project", "purpose": "container for product idea and generated backend", "relevance_score": 5},
        {"name": "Spec", "purpose": "versioned domain specification submitted by user", "relevance_score": 5},
        {"name": "Workflow", "purpose": "tracks user-facing action flows and states", "relevance_score": 4},
        {"name": "ValidationRule", "purpose": "captures business constraints applied to domain actions", "relevance_score": 4},
    ]
    structured_payload = {
        "product_summary": summary,
        "user_roles": [
            {
                "name": "Primary User",
                "responsibilities": [
                    "Submit product idea",
                    "Review generated backend blueprint",
                    "Refine and regenerate based on feedback",
                ],
            }
        ],
        "core_workflows": [
            {
                "name": "Idea Submission",
                "steps": [
                    "User enters idea description",
                    "System validates and normalizes input",
                    "Specification becomes generation-ready",
                ],
                "state_changes": ["idea_draft->idea_submitted", "spec_pending->spec_ready"],
            },
            {
                "name": "Blueprint Generation",
                "steps": [
                    "System derives entities and relationships",
                    "System drafts schema and API design",
                    "User receives generated output",
                ],
                "state_changes": ["pipeline_queued->pipeline_completed"],
            },
            {
                "name": "Revision Cycle",
                "steps": [
                    "User reviews output and edits idea",
                    "System revalidates constraints",
                    "System publishes refreshed artifacts",
                ],
                "state_changes": ["output_published->output_revised"],
            },
        ],
        "entities": entities,
        "relationships": [
            "User 1..* Project",
            "Project 1..* Spec",
            "Spec 1..* Workflow",
            "Workflow *..* ValidationRule",
        ],
        "business_rules": [
            "Only valid input can transition from draft to submitted state",
            "Every workflow transition must satisfy at least one validation rule",
            "Regeneration must preserve project ownership and version history",
        ],
        "edge_cases": [
            "Empty or vague idea input should produce actionable validation guidance",
            "Duplicate regeneration requests should be idempotent at output level",
            "Invalid state transitions must be rejected with clear reason",
        ],
    }

    rendered = _render_expansion_spec(base, structured_payload)
    expanded = str(rendered.get("expanded_spec") or "")
    inferred = rendered.get("inferred_items") if isinstance(rendered.get("inferred_items"), list) else []

    while len(expanded) < target_chars:
        expanded += "\n\n- Additional inferred behavior: apply strict user-facing validation before business state updates."
        if len(expanded) > target_chars + 250:
            break

    return {
        "expanded_spec": expanded[: max(target_chars, len(base) + 300)],
        "inferred_items": inferred,
        "source": "heuristic",
    }


def _expand_spec_with_groq(content: str, model: str, target_chars: int = 6500, plan_code: str | None = None) -> Dict[str, Any]:
    normalized_plan = str(plan_code or "").strip().lower()
    is_enterprise = normalized_plan == "enterprise"
    prompt = (
        "You are a backend system correction engine. "
        "You are NOT generating a system from scratch. "
        "You are REFINING an existing expanded specification. "
        "Your job is to REMOVE incorrect abstractions and produce a clean, domain-specific backend. "
        "PHASE 1: DETECT PROBLEMS. Identify entities not part of product domain including orchestration, "
        "internal mechanics, infrastructure, and generic abstractions. "
        "PHASE 2: APPLY HARD FILTER. Remove entities that are not product functionality, not user-facing workflow, "
        "cannot be explained in product terms, or are implementation details. "
        "PHASE 3: ENTITY VALIDATION. Each remaining entity must join a workflow, connect to another entity, and be a real business concept. "
        "PHASE 4: DOMAIN REBUILD around user actions, business objects, and product workflows only. "
        "PHASE 5: COMPLETENESS CHECK for actors, core objects, transactions where applicable, and only necessary support entities. "
        "PHASE 6: COMPLEXITY CONTROL with entity count minimum 20 and maximum 45. "
        "PHASE 7: FINAL VALIDATION reject meta/framework entities and disconnected entities before return. "
        "Return ONLY JSON with keys exactly: "
        "invalid_entities_removed (string[]), "
        "final_entities (array of {name,purpose}), "
        "relationships (string[]), "
        "workflows (string[] or array of {name,steps,state_changes}), "
        "business_rules (string[]), "
        "edge_cases (string[]). "
        "Use concrete domain naming and avoid framework wording. "
        f"\n\nINPUT:\n{content}"
    )
    if is_enterprise:
        prompt += (
            "\n\nPHASE 8: ENTITY SIMPLIFICATION (CRITICAL). "
            "Review all entities and identify over-fragmentation. "
            "Merge entities that represent the same concept split into multiple parts, differ only by metadata/state/config, "
            "or can exist as fields rather than separate tables. "
            "Prefer richer entities over many smaller ones and merge entities always used together. "
            "\nPHASE 9: FINAL SANITY CHECK. "
            "Ensure no concept is unnecessarily split, each entity is meaningful and distinct, and the result is understandable by a backend engineer. "
            "If over-engineered, simplify further. "
            "\nPHASE X: ENTITY NECESSITY CHECK. "
            "For each entity, ask if it requires independent lifecycle, querying, or relationships. "
            "If NO, convert it into a field, enum, or JSON structure and do not keep it as a separate entity. "
            "Treat status/type/configuration/rule-like concepts as field-level by default unless strong relational necessity exists. "
            "\nFINAL PHASE: SENIOR ENGINEERING REVIEW. "
            "Act as a production-readiness reviewer focused on simplification and optimization, not expansion. "
            "Re-run entity necessity checks, merge redundant concepts aggressively, and reduce over-normalization. "
            "The resulting model must be understandable in 2-3 minutes and implementable without confusion. "
            "For enterprise quality, target 20-35 entities, with hard maximum 40 only if strongly justified."
        )
    raw = _call_groq_chat(
        [
            {"role": "system", "content": "Return only JSON."},
            {"role": "user", "content": prompt},
        ],
        model=model,
        timeout=60,
    )

    rendered = _render_expansion_spec(content, raw, plan_code=plan_code)
    expanded_spec = str(rendered.get("expanded_spec") or "").strip()
    inferred_items = rendered.get("inferred_items") if isinstance(rendered.get("inferred_items"), list) else []

    if not expanded_spec:
        raise ValueError("Expanded spec rendering failed")

    return {
        "expanded_spec": expanded_spec,
        "inferred_items": inferred_items[:32],
        "source": "groq",
        "model": model,
    }


def expand_spec_for_pipeline(content: str, plan_code: str | None = None) -> Dict[str, Any]:
    base = str(content or "").strip()
    if not base:
        return {
            "expanded_spec": "",
            "source": "none",
            "model": None,
            "original_chars": 0,
            "expanded_chars": 0,
            "inferred_count": 0,
        }

    model_candidates: List[str] = []
    if settings.groq_model:
        model_candidates.append(settings.groq_model)
    if settings.groq_fallback_model and settings.groq_fallback_model not in model_candidates:
        model_candidates.append(settings.groq_fallback_model)

    for model in model_candidates:
        try:
            expanded = _expand_spec_with_groq(base, model=model, plan_code=plan_code)
            expanded_spec = str(expanded.get("expanded_spec") or "").strip()
            if len(expanded_spec) >= max(1200, len(base)):
                logger.info(
                    "[PIPELINE] spec.expand.success source=groq model=%s original_chars=%s expanded_chars=%s inferred=%s",
                    model,
                    len(base),
                    len(expanded_spec),
                    len(expanded.get("inferred_items") or []),
                )
                return {
                    "expanded_spec": expanded_spec,
                    "source": "groq",
                    "model": model,
                    "original_chars": len(base),
                    "expanded_chars": len(expanded_spec),
                    "inferred_count": len(expanded.get("inferred_items") or []),
                }
        except Exception as error:
            logger.warning("[PIPELINE] spec.expand.model_failed model=%s error=%s", model, error)
            continue

    fallback = _heuristic_expand_spec(base)
    expanded_spec = str(fallback.get("expanded_spec") or base)
    logger.info(
        "[PIPELINE] spec.expand.fallback source=%s original_chars=%s expanded_chars=%s inferred=%s",
        fallback.get("source", "heuristic"),
        len(base),
        len(expanded_spec),
        len(fallback.get("inferred_items") or []),
    )
    return {
        "expanded_spec": expanded_spec,
        "source": fallback.get("source", "heuristic"),
        "model": None,
        "original_chars": len(base),
        "expanded_chars": len(expanded_spec),
        "inferred_count": len(fallback.get("inferred_items") or []),
    }


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
    deduped = _dedupe_endpoints(sanitized)

    lower_content = (content or "").lower()
    entity_names = {str(entity.get("name", "")).strip().lower() for entity in entities if str(entity.get("name", "")).strip()}
    if "lender" in entity_names and "portfolio" in lower_content and ("performance" in lower_content or "interest" in lower_content):
        deduped = _dedupe_endpoints(
            deduped
            + [
                {
                    "method": "GET",
                    "path": "/lenders/{id}/portfolio",
                    "desc": "Get lender portfolio performance (total funded, active loans, total interest earned, default rate)",
                    "errors": ["lender_not_found"],
                }
            ]
        )

    return deduped


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
def _generate_migration_sql_batched(entities: List[Dict[str, Any]], relationships: List[str], join_tables: List[Dict[str, Any]], model: str) -> str:
    entity_map: Dict[str, List[Dict[str, Any]]] = {
        str(entity.get("name", "")).strip(): entity.get("fields") or []
        for entity in entities
        if str(entity.get("name", "")).strip()
    }
    entity_names = list(entity_map.keys())
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
        batch_entities = [{"name": name, "fields": entity_map.get(name, [])} for name in batch]
        expected = len(batch)
        warning = ""

        for attempt in range(2):
            prompt = (
                "Return JSON with key migration_sql only. "
                "Generate CREATE TABLE for ALL entities listed. Do not stop early. "
                f"If there are N entities, there must be exactly N CREATE TABLE statements. N={expected}. "
                "Each CREATE TABLE must include all provided fields (not only id/created_at). "
                f"Entities with fields: {json.dumps(batch_entities)}. Relationships context: {json.dumps(relationships)}. Join tables context: {json.dumps(join_tables)}. "
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


def _to_snake_case(name: str) -> str:
    value = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    value = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", value).replace("-", "_")
    value = re.sub(r"\s+", "_", value)
    return value.lower().strip("_")


def _pluralize(name: str) -> str:
    if name.endswith("y") and len(name) > 1 and name[-2] not in "aeiou":
        return f"{name[:-1]}ies"
    if name.endswith("s"):
        return name
    return f"{name}s"


def _normalize_type(value: str) -> str:
    lowered = str(value or "").strip().lower()
    if lowered in {"int", "integer", "bigint", "smallint"}:
        return "integer"
    if lowered in {"uuid", "text", "numeric", "boolean", "date", "jsonb", "timestamptz", "timestamp"}:
        return "timestamptz" if lowered == "timestamp" else lowered
    return lowered or "text"


def _extract_primary_key_type(entity: Dict[str, Any]) -> str:
    for field in entity.get("fields") or []:
        constraints = field.get("constraints") or []
        if str(field.get("name", "")).lower() == "id" or "primary_key" in constraints:
            return _normalize_type(str(field.get("type", "uuid")))
    return "uuid"


def _guess_target_entity_id(field_name: str, known_entities: Dict[str, Dict[str, Any]]) -> Optional[str]:
    if not field_name.endswith("_id"):
        return None
    base = field_name[:-3]
    direct = known_entities.get(base)
    if direct:
        return base
    singular = base[:-1] if base.endswith("s") else base
    if singular in known_entities:
        return singular
    compact = base.replace("_", "")
    for key in known_entities.keys():
        if key.replace("_", "") == compact:
            return key
    return None


def _align_entity_field_types(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    lookup: Dict[str, Dict[str, Any]] = {
        _to_snake_case(str(entity.get("name", ""))): entity
        for entity in entities
        if str(entity.get("name", "")).strip()
    }
    pk_types: Dict[str, str] = {key: _extract_primary_key_type(entity) for key, entity in lookup.items()}

    aligned: List[Dict[str, Any]] = []
    for entity in entities:
        fields = []
        for field in entity.get("fields") or []:
            name = str(field.get("name", "")).strip()
            current_type = _normalize_type(str(field.get("type", "text")))
            constraints = field.get("constraints") or []
            target = _guess_target_entity_id(name.lower(), lookup)
            if target and ("foreign_key" in constraints or name.lower().endswith("_id")):
                current_type = pk_types.get(target, current_type)
            fields.append({"name": name, "type": current_type, "constraints": constraints})
        aligned.append({"name": entity.get("name"), "fields": fields})
    return aligned


def _ensure_join_table_minimum_fields(join_tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    fixed: List[Dict[str, Any]] = []
    for table in join_tables:
        name = str(table.get("name", "")).strip()
        if not name:
            continue
        left_entity = str(table.get("left_entity", "")).strip()
        right_entity = str(table.get("right_entity", "")).strip()
        existing = [str(field).strip() for field in (table.get("fields") or []) if str(field).strip()]

        def _column_name(fragment: str) -> Optional[str]:
            text = str(fragment or "").strip().strip(",")
            if not text:
                return None
            lowered = text.lower()
            if lowered.startswith(("primary key", "foreign key", "constraint", "unique(", "check(")):
                return None
            return text.split()[0].strip('"').lower()

        by_column: Dict[str, str] = {}
        passthrough: List[str] = []
        for field in existing:
            col = _column_name(field)
            if col:
                by_column[col] = field
            else:
                passthrough.append(field)

        def _canonical_fk_column(entity_name: str) -> str:
            return f"{_to_snake_case(entity_name)}_id"

        def _compact(text: str) -> str:
            return re.sub(r"[^a-z0-9]", "", text.lower())

        if left_entity:
            canonical_left = _canonical_fk_column(left_entity)
            left_compact = _compact(canonical_left)
            for existing_col in list(by_column.keys()):
                if existing_col.endswith("_id") and _compact(existing_col) == left_compact and existing_col != canonical_left:
                    by_column[canonical_left] = by_column.pop(existing_col)

        if right_entity:
            canonical_right = _canonical_fk_column(right_entity)
            right_compact = _compact(canonical_right)
            for existing_col in list(by_column.keys()):
                if existing_col.endswith("_id") and _compact(existing_col) == right_compact and existing_col != canonical_right:
                    by_column[canonical_right] = by_column.pop(existing_col)

        def _upsert_column(column_name: str, field_sql: str) -> None:
            if column_name not in by_column:
                by_column[column_name] = field_sql

        def _ensure_fk_reference(column_name: str, entity_name: str) -> None:
            if column_name not in by_column:
                return
            field_sql = by_column[column_name]
            if "references" in field_sql.lower():
                return
            target_table = _pluralize(_to_snake_case(entity_name))
            if len(field_sql.split()) == 1:
                by_column[column_name] = f"{column_name} uuid not null references {target_table}(id)"
            else:
                by_column[column_name] = f"{field_sql} references {target_table}(id)"

        def _is_valid_field_sql(field_sql: str) -> bool:
            text = str(field_sql or "").strip().strip(",")
            if not text:
                return False
            lowered = text.lower()
            if lowered.startswith(("primary key", "foreign key", "constraint", "unique(", "check(")):
                return True
            # Drop malformed bare tokens like "usage_id" with no type/definition.
            return any(ch.isspace() for ch in text)

        default_fields = [
            "id uuid primary key default gen_random_uuid()",
        ]
        if left_entity:
            default_fields.append(f"{_canonical_fk_column(left_entity)} uuid not null references {_pluralize(_to_snake_case(left_entity))}(id)")
        if right_entity:
            default_fields.append(f"{_canonical_fk_column(right_entity)} uuid not null references {_pluralize(_to_snake_case(right_entity))}(id)")
        default_fields.append("created_at timestamptz not null default now()")

        for field in default_fields:
            base_name = field.split(" ")[0].lower()
            _upsert_column(base_name, field)

        if left_entity:
            _ensure_fk_reference(_canonical_fk_column(left_entity), left_entity)
        if right_entity:
            _ensure_fk_reference(_canonical_fk_column(right_entity), right_entity)

        is_loan_lender = {left_entity.lower(), right_entity.lower()} == {"loan", "lender"} or _to_snake_case(name) in {"loan_lender", "loan_lenders"}
        if is_loan_lender:
            _upsert_column("funded_amount", "funded_amount numeric not null")
            _upsert_column("funded_at", "funded_at timestamptz")
            _upsert_column("percentage_funded", "percentage_funded numeric")

        ordered_columns: List[str] = []
        preferred_order = [
            "id",
            _canonical_fk_column(left_entity) if left_entity else "",
            _canonical_fk_column(right_entity) if right_entity else "",
            "funded_amount",
            "funded_at",
            "percentage_funded",
            "created_at",
        ]
        for column in preferred_order:
            if column and column in by_column:
                ordered_columns.append(by_column.pop(column))

        ordered_columns.extend(by_column.values())
        ordered_columns.extend(passthrough)
        ordered_columns = [field for field in ordered_columns if _is_valid_field_sql(field)]

        fixed.append(
            {
                "name": name,
                "left_entity": left_entity,
                "right_entity": right_entity,
                "purpose": str(table.get("purpose", "")).strip(),
                "fields": ordered_columns,
            }
        )
    return fixed


def _extract_sql_table_columns(sql: str) -> Dict[str, Set[str]]:
    table_columns: Dict[str, Set[str]] = {}
    pattern = re.compile(r"create\s+table\s+(?:if\s+not\s+exists\s+)?([a-zA-Z0-9_]+)\s*\((.*?)\);", re.IGNORECASE | re.DOTALL)

    def _normalize_table_name(name: str) -> str:
        return _to_snake_case(str(name or "").strip().strip('"')).lower()

    for match in pattern.finditer(sql or ""):
        table_name = _normalize_table_name(match.group(1))
        body = str(match.group(2))
        columns: Set[str] = set()
        for raw_line in body.splitlines():
            line = raw_line.strip().strip(",")
            if not line:
                continue
            if line.lower().startswith(("primary key", "foreign key", "constraint", "unique(", "check(")):
                continue
            parts = line.split()
            if parts:
                columns.add(parts[0].strip('"').lower())
        table_columns[table_name] = columns
    return table_columns


def _find_matching_table(entity_name: str, tables: Set[str]) -> Optional[str]:
    base = _to_snake_case(entity_name)
    candidates = [base, _pluralize(base)]
    for candidate in candidates:
        normalized = _to_snake_case(candidate)
        if normalized in tables:
            return normalized
        if candidate in tables:
            return candidate
    return None


def _render_field_sql(field: Dict[str, Any]) -> str:
    field_name = str(field.get("name", "")).strip().lower()
    field_type = _normalize_type(str(field.get("type", "text")))
    return f"{field_name} {field_type}"


def _append_join_tables_sql(migration_sql: str, join_tables: List[Dict[str, Any]]) -> str:
    sql = migration_sql or ""
    for table in join_tables:
        table_name = _pluralize(_to_snake_case(str(table.get("name", "")).strip()))
        if not table_name:
            continue
        if re.search(rf"create\s+table\s+(?:if\s+not\s+exists\s+)?{re.escape(table_name)}\b", sql, flags=re.IGNORECASE):
            continue

        fields = [str(item).strip() for item in (table.get("fields") or []) if str(item).strip()]
        if not fields:
            continue
        field_block = ",\n  ".join(fields)
        sql += (
            "\n\n"
            f"create table if not exists {table_name} (\n"
            f"  {field_block}\n"
            ");"
        )
    return sql


def _reconcile_migration_sql(migration_sql: str, entities: List[Dict[str, Any]], join_tables: List[Dict[str, Any]]) -> str:
    sql = _append_join_tables_sql(migration_sql, join_tables)
    table_columns = _extract_sql_table_columns(sql)
    table_names = set(table_columns.keys())
    if not table_names:
        return sql

    patches: List[str] = []
    for entity in entities:
        entity_name = str(entity.get("name", "")).strip().lower().replace(" ", "_")
        table_name = _find_matching_table(entity_name, table_names)
        if not table_name:
            continue

        existing = table_columns.get(table_name, set())
        for field in entity.get("fields") or []:
            field_name = str(field.get("name", "")).strip().lower()
            if not field_name or field_name in existing:
                continue
            patches.append(
                f"alter table if exists {table_name} add column if not exists {_render_field_sql(field)};"
            )

    if patches:
        sql += "\n\n-- Reconciliation patch: add missing ERD columns\n" + "\n".join(patches)
    return sql


def _normalize_create_table_defaults(sql: str) -> str:
    lines = (sql or "").splitlines()
    normalized: List[str] = []

    for raw_line in lines:
        line = raw_line
        comma = "," if raw_line.rstrip().endswith(",") else ""
        stripped = raw_line.strip().rstrip(",")
        lowered = stripped.lower()

        if re.match(r"^id\s+uuid\s+primary\s+key\b", lowered) and "default" not in lowered:
            indent = raw_line[: len(raw_line) - len(raw_line.lstrip())]
            line = f"{indent}id uuid primary key default gen_random_uuid(){comma}"
        elif re.match(r"^created_at\s+timestamptz\s+not\s+null\b", lowered) and "default" not in lowered:
            indent = raw_line[: len(raw_line) - len(raw_line.lstrip())]
            line = f"{indent}created_at timestamptz not null default now(){comma}"

        normalized.append(line)

    return "\n".join(normalized)


def _sanitize_blueprint(raw: Dict[str, Any], content: str) -> Dict[str, Any]:
    entities_raw = raw.get("entities") if isinstance(raw.get("entities"), list) else []
    if not entities_raw and isinstance(raw.get("final_entities"), list):
        entities_raw = [
            {
                "name": str(item.get("name") or "").strip(),
                "fields": _default_fields_for_entity(str(item.get("name") or "")),
            }
            for item in raw.get("final_entities")
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        ]
    endpoints_raw = raw.get("endpoints") if isinstance(raw.get("endpoints"), list) else []
    rules_raw = raw.get("rules") if isinstance(raw.get("rules"), list) else []
    if not rules_raw and isinstance(raw.get("business_rules"), list):
        rules_raw = raw.get("business_rules")
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
    entities = _ensure_entity_field_depth(entities, content)
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


def _call_groq_for_blueprint(content: str, model: str, plan_code: str | None = None) -> Dict[str, Any]:
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

    if str(plan_code or "").strip().lower() == "creator":
        system_prompt += (
            " CREATOR CORRECTION - BALANCED VERSION: "
            "This task is fully isolated. Use ONLY current specification; do not reuse entities from previous runs. "
            "If any unrelated entity appears, remove it before returning. "
            "Remove invalid/internal fields like relevance_score/confidence/reasoning/internal scoring metadata from final schema. "
            "Remove meta/system entities (workflow/pipeline/engine/state machine/process/infrastructure abstractions). "
            "Prevent over-simplification: keep valid business concepts, transactional records, relationship entities, and useful logs/history. "
            "Run entity necessity check: keep entities with clear product purpose and workflow support, convert to fields only when label-only or without lifecycle. "
            "Avoid over-splitting relationships; merge access control into share when appropriate (Share with permission_type). "
            "Merge duplicates carefully (Admin+Member -> GroupMember with role). "
            "Do NOT merge distinct concepts like Expense vs Settlement or Expense vs Split. "
            "For expense domains ensure completeness with User, Group, GroupMember, Expense, ExpenseSplit, Settlement; optional Balance/ActivityLog/Transaction. "
            "For file-sharing domains keep only domain entities like User/File/Folder/Share/Version/ActivityLog and remove finance/project-management entities. "
            "PRECISION BACKEND GENERATION: one concept equals one entity and no field duplication. "
            "If Activity and ActivityLog both exist, keep only one canonical ActivityLog. "
            "Do not keep permission json, permissions arrays, and permission tables when Share already has permission_type. "
            "Share schema should be simple: resource_id, resource_type, owner_user_id, target_user_id nullable, permission_type, expiration_time optional. "
            "Version should only include file_id, version_number, created_at. "
            "Avoid generic filler fields like status/name when they are not meaningful to that entity. "
            "Target creator systems around 6-12 meaningful entities. "
            "Final output must be clean, complete, practical, and ready to implement."
        )

    if str(plan_code or "").strip().lower() == "studio":
        system_prompt += (
            " You are NOT generating a backend spec. You are auditing and rebuilding an incomplete system into a production-grade architecture. "
            "PHASE 0 failure detection: if system has fewer than 18 entities, lacks ledger transaction system, mixes financial and domain logic, lacks usage-vs-billing separation, or lacks lifecycle states, mark as UNDER-SPECIFIED and expand. "
            "PHASE 1 structural rebuild with mandatory layers: Core Domain (Organization, User, Role, Product, Plan, Subscription), Usage (UsageEvent, UsageAggregate), Billing (BillingCycle, Invoice, InvoiceLineItem), Financial (Transaction ledger, Payment, PaymentAttempt, Refund, Balance/Account), Pricing (PricingRule, Meter/Metric definition), Support (Notification, immutable AuditLog). "
            "PHASE 2 relationship enforcement: UsageEvent to UsageAggregate to InvoiceLineItem to Invoice; Invoice to Payment to Transaction; Subscription to BillingCycle to Invoice. Remove shortcuts. "
            "PHASE 3 lifecycle modeling: Subscription trial/active/past_due/canceled/expired, Invoice draft/finalized/paid/failed/void, Payment pending/succeeded/failed/retried. "
            "PHASE 4 entity quality control: clear purpose and relevance score, remove vague helper/UI entities, target 18 to 30 entities. "
            "PHASE 5 output structure should include system_status, invalid_entities_removed, final_entities, relationships, workflows, business_rules, edge_cases. "
            "Critical rules: do not simplify away financial separation, include transaction ledger behavior, include usage aggregation, and avoid CRUD-only outputs."
        )

    if str(plan_code or "").strip().lower() == "growth":
        system_prompt += (
            " You are NOT generating entities from scratch. "
            "You are refining an existing backend specification into a production-grade transactional system. "
            "Your goal is NOT to simplify; your goal is to enforce correct system architecture. "
            "PHASE 1: remove invalid/shallow structures such as mixed financial and business logic, UI-level concepts, lifecycle-less entities, and duplicated responsibilities. "
            "Track removed entities as invalid_entities_removed. "
            "PHASE 2: enforce system layers with core domain (User, Project, Proposal, Contract), orchestration (Milestone, MilestoneAssignment, MilestoneSubmission, MilestoneState), financial (EscrowAccount, Transaction, Payout, Refund), dispute (Dispute, DisputeMessage, Evidence, Resolution), trust (Review, rating aggregation), and support (Notification, AuditLog). "
            "PHASE 3: enforce relationship correctness with financial flow EscrowAccount to Transaction to Payout or Refund, milestone not directly holding money state, independent submissions, and non-flat disputes. "
            "PHASE 4: entity quality control requiring clear purpose, responsibility boundaries, relevance_score 1-5, and removing vague helper entities (calculator/engine). "
            "PHASE 5: return structured JSON with invalid_entities_removed, final_entities, relationships, workflows, business_rules, and edge_cases. "
            "Critical rules: do not collapse systems just for count reduction, do not merge financial logic into domain entities, do not oversimplify dispute or transaction flow, keep total entities between 18 and 30. "
            "For runtime compatibility in addition to final_entities also provide entities with fields when possible."
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


def _ensure_field(entity: Dict[str, Any], field_name: str, field_type: str, constraints: Optional[List[str]] = None) -> None:
    fields = entity.get("fields") if isinstance(entity.get("fields"), list) else []
    normalized_fields = [_normalize_field(item) for item in fields]
    normalized_fields = [item for item in normalized_fields if item]

    existing_index = {
        str(item.get("name", "")).strip().lower(): idx for idx, item in enumerate(normalized_fields)
    }
    normalized_name = field_name.strip().lower()
    candidate = {
        "name": normalized_name,
        "type": _normalize_type(field_type),
        "constraints": list(dict.fromkeys(constraints or [])),
    }

    if normalized_name in existing_index:
        index = existing_index[normalized_name]
        merged_constraints = list(
            dict.fromkeys((normalized_fields[index].get("constraints") or []) + candidate["constraints"])
        )
        normalized_fields[index]["constraints"] = merged_constraints
        if not normalized_fields[index].get("type"):
            normalized_fields[index]["type"] = candidate["type"]
    else:
        normalized_fields.append(candidate)

    entity["fields"] = normalized_fields


def _sanitize_schema_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    remove_fields = {"relevance_score", "confidence", "score", "reasoning"}
    sanitized: List[Dict[str, Any]] = []
    for entity in entities:
        if not isinstance(entity, dict):
            continue
        fields = entity.get("fields") if isinstance(entity.get("fields"), list) else []
        cleaned_fields: List[Dict[str, Any]] = []
        seen_field_names: Set[str] = set()
        for field in fields:
            normalized = _normalize_field(field)
            if not normalized:
                continue
            field_name = str(normalized.get("name", "")).strip().lower()
            if not field_name or field_name in remove_fields or field_name in seen_field_names:
                continue
            seen_field_names.add(field_name)
            cleaned_fields.append(normalized)
        clone = dict(entity)
        clone["fields"] = cleaned_fields
        sanitized.append(clone)
    return sanitized


def _normalize_creator_role_entities(entities: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    items = [dict(entity) for entity in entities if isinstance(entity, dict)]
    by_key = {
        _to_snake_case(str(entity.get("name") or "")): entity
        for entity in items
        if str(entity.get("name") or "").strip()
    }

    group_member = by_key.get("group_member")
    member_alias = by_key.get("member")
    admin_alias = by_key.get("group_admin") or by_key.get("admin")

    if group_member or member_alias or admin_alias:
        if not group_member:
            group_member = {
                "name": "GroupMember",
                "fields": [],
            }
            items.append(group_member)

        _ensure_field(group_member, "id", "uuid", ["primary_key"])
        _ensure_field(group_member, "group_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(group_member, "user_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(group_member, "role", "text", ["not_null"])
        _ensure_field(group_member, "joined_at", "timestamptz", ["not_null"])

        remove_names = {"member", "group_admin", "admin"}
        items = [
            entity
            for entity in items
            if _to_snake_case(str(entity.get("name") or "")) not in remove_names
        ]

    return items


def _detect_creator_domain(content: str, entities: List[Dict[str, Any]]) -> str:
    lowered = str(content or "").lower()
    entity_names = {
        _to_snake_case(str(item.get("name") or ""))
        for item in entities
        if isinstance(item, dict) and str(item.get("name") or "").strip()
    }

    file_hits = sum(
        1
        for token in ["file", "folder", "upload", "download", "share", "version", "public link", "storage"]
        if token in lowered
    )
    expense_hits = sum(
        1
        for token in ["expense", "split", "settlement", "group", "owe", "balance"]
        if token in lowered
    )

    if file_hits >= 2 or entity_names.intersection({"file", "folder", "share", "version"}):
        return "file_sharing"
    if expense_hits >= 2 or entity_names.intersection({"expense", "split", "expense_split", "settlement"}):
        return "expense"
    return "generic"


def _set_entity_fields(entity: Dict[str, Any], desired_fields: List[Dict[str, Any]]) -> None:
    normalized: List[Dict[str, Any]] = []
    seen: Set[str] = set()
    for field in desired_fields:
        parsed = _normalize_field(field)
        if not parsed:
            continue
        key = str(parsed.get("name", "")).strip().lower()
        if not key or key in seen:
            continue
        seen.add(key)
        normalized.append(parsed)
    entity["fields"] = normalized


def _apply_creator_file_precision(entities: List[Dict[str, Any]], relationships: List[str]) -> tuple[List[Dict[str, Any]], List[str]]:
    items = [dict(entity) for entity in entities if isinstance(entity, dict)]
    by_key = {
        _to_snake_case(str(entity.get("name") or "")): entity
        for entity in items
        if str(entity.get("name") or "").strip()
    }

    # One concept = one entity: keep only ActivityLog.
    if "activity" in by_key and "activity_log" in by_key:
        items = [
            entity
            for entity in items
            if _to_snake_case(str(entity.get("name") or "")) != "activity"
        ]
        by_key.pop("activity", None)

    activity_log = by_key.get("activity_log") or by_key.get("activity")
    if activity_log:
        activity_log["name"] = "ActivityLog"
        _set_entity_fields(
            activity_log,
            [
                {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "action_type", "type": "text", "constraints": ["not_null"]},
                {"name": "entity_type", "type": "text", "constraints": ["not_null"]},
                {"name": "entity_id", "type": "uuid", "constraints": ["not_null"]},
                {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
            ],
        )

    # Share + Permission should collapse into Share with permission_type.
    if "permission" in by_key:
        items = [
            entity
            for entity in items
            if _to_snake_case(str(entity.get("name") or "")) != "permission"
        ]
        by_key.pop("permission", None)

    share = by_key.get("share")
    if share:
        _set_entity_fields(
            share,
            [
                {"name": "resource_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "resource_type", "type": "text", "constraints": ["not_null"]},
                {"name": "owner_user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "target_user_id", "type": "uuid", "constraints": ["foreign_key"]},
                {"name": "permission_type", "type": "text", "constraints": ["not_null"]},
                {"name": "expiration_time", "type": "timestamptz", "constraints": []},
            ],
        )

    version = by_key.get("version")
    if version:
        _set_entity_fields(
            version,
            [
                {"name": "file_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "version_number", "type": "integer", "constraints": ["not_null"]},
                {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
            ],
        )

    folder = by_key.get("folder")
    if folder:
        folder_fields = folder.get("fields") if isinstance(folder.get("fields"), list) else []
        folder["fields"] = [
            field
            for field in (_normalize_field(item) for item in folder_fields)
            if field and str(field.get("name") or "").strip().lower() not in {"permissions", "permissions_json", "permission_json", "status"}
        ]

    relationships_out = _dedupe_strings(
        [
            rel
            for rel in relationships
            if rel
            and "permission" not in rel.lower()
            and not ("activity" in rel.lower() and "activitylog" not in rel.lower() and "ActivityLog" not in rel)
        ]
        + [
            "User 1..* Folder",
            "Folder 1..* File",
            "File 1..* Share",
            "File 1..* Version",
            "User 1..* ActivityLog",
        ]
    )

    return items, relationships_out


def _find_entity_by_keys(entities: List[Dict[str, Any]], keys: Set[str]) -> Optional[Dict[str, Any]]:
    for entity in entities:
        name = _to_snake_case(str(entity.get("name") or ""))
        if name in keys:
            return entity
    return None


def _add_entity_if_missing(entities: List[Dict[str, Any]], name: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
    key = _to_snake_case(name)
    existing = _find_entity_by_keys(entities, {key})
    if existing:
        return existing
    entity = {"name": name, "fields": []}
    _set_entity_fields(entity, fields)
    entities.append(entity)
    return entity


def _apply_studio_depth_refinement(blueprint: Dict[str, Any], content: str) -> Dict[str, Any]:
    entities = blueprint.get("entities") if isinstance(blueprint.get("entities"), list) else []
    relationships = blueprint.get("relationships") if isinstance(blueprint.get("relationships"), list) else []
    if not entities:
        return blueprint

    lowered = str(content or "").lower()
    transactional_cues = ["order", "cart", "checkout", "booking", "reservation", "marketplace"]
    variant_cues = ["variant", "size", "color", "sku", "attribute"]
    multi_actor_cues = ["vendor", "seller", "merchant", "provider", "host", "multi-vendor", "multi seller"]
    process_cues = ["workflow", "approval", "step", "stage", "pipeline", "review flow", "state transition"]

    has_transactional_domain = any(cue in lowered for cue in transactional_cues)
    has_variant_domain = any(cue in lowered for cue in variant_cues)
    has_multi_actor = any(cue in lowered for cue in multi_actor_cues)
    has_process_domain = any(cue in lowered for cue in process_cues)

    order = _find_entity_by_keys(entities, {"order", "booking", "reservation"})
    product = _find_entity_by_keys(entities, {"product", "item", "listing"})
    order_item = _find_entity_by_keys(entities, {"order_item", "booking_slot", "cart_item", "line_item"})

    if has_transactional_domain and order and not order_item:
        order_item = _add_entity_if_missing(
            entities,
            "OrderItem",
            [
                {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
                {"name": "order_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "product_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "quantity", "type": "integer", "constraints": ["not_null"]},
                {"name": "unit_price", "type": "numeric", "constraints": ["not_null"]},
                {"name": "line_total", "type": "numeric", "constraints": ["not_null"]},
            ],
        )

    product_variant = _find_entity_by_keys(entities, {"product_variant", "variant"})
    if has_variant_domain and product and not product_variant:
        product_variant = _add_entity_if_missing(
            entities,
            "ProductVariant",
            [
                {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
                {"name": "product_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "sku", "type": "text", "constraints": ["unique", "not_null"]},
                {"name": "attributes", "type": "jsonb", "constraints": ["not_null"]},
                {"name": "price", "type": "numeric", "constraints": ["not_null"]},
                {"name": "stock", "type": "integer", "constraints": ["not_null"]},
            ],
        )

    inventory = _find_entity_by_keys(entities, {"inventory", "stock"})
    if product_variant:
        if inventory:
            _ensure_field(inventory, "product_variant_id", "uuid", ["foreign_key", "not_null"])
            fields = inventory.get("fields") if isinstance(inventory.get("fields"), list) else []
            inventory["fields"] = [
                field
                for field in (_normalize_field(item) for item in fields)
                if field and str(field.get("name") or "").strip().lower() != "product_id"
            ]
        if order_item:
            _ensure_field(order_item, "product_variant_id", "uuid", ["foreign_key"])

    if has_multi_actor and order_item:
        _ensure_field(order_item, "seller_id", "uuid", ["foreign_key"])

    workflow = _find_entity_by_keys(entities, {"workflow", "process_flow", "approval_flow"})
    step = _find_entity_by_keys(entities, {"step", "workflow_step", "process_step"})
    if has_process_domain and workflow and not step:
        step = _add_entity_if_missing(
            entities,
            "Step",
            [
                {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
                {"name": "workflow_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "step_order", "type": "integer", "constraints": ["not_null"]},
                {"name": "step_type", "type": "text", "constraints": ["not_null"]},
                {"name": "assigned_role_id", "type": "uuid", "constraints": ["foreign_key"]},
                {"name": "assigned_user_id", "type": "uuid", "constraints": ["foreign_key"]},
            ],
        )
    if workflow and step:
        _ensure_field(step, "workflow_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(step, "step_order", "integer", ["not_null"])
        _ensure_field(step, "step_type", "text", ["not_null"])
        _ensure_field(step, "assigned_role_id", "uuid", ["foreign_key"])
        _ensure_field(step, "assigned_user_id", "uuid", ["foreign_key"])

    payment = _find_entity_by_keys(entities, {"payment"})
    dispute = _find_entity_by_keys(entities, {"dispute"})
    if order:
        _ensure_field(order, "status", "text", ["not_null"])
    if payment:
        _ensure_field(payment, "status", "text", ["not_null"])
    if dispute:
        _ensure_field(dispute, "status", "text", ["not_null"])

    # Unified audit/traceability: keep one AuditLog and collapse activity-like entities.
    activity_like_keys = {"activity", "activity_log", "audit", "audit_log", "event_log"}
    audit_anchor = _find_entity_by_keys(entities, activity_like_keys)
    if audit_anchor:
        audit_anchor["name"] = "AuditLog"
        _set_entity_fields(
            audit_anchor,
            [
                {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "action_type", "type": "text", "constraints": ["not_null"]},
                {"name": "entity_type", "type": "text", "constraints": ["not_null"]},
                {"name": "entity_id", "type": "uuid", "constraints": ["not_null"]},
                {"name": "timestamp", "type": "timestamptz", "constraints": ["not_null"]},
            ],
        )
        entities = [
            entity
            for entity in entities
            if _to_snake_case(str(entity.get("name") or "")) not in activity_like_keys
            or entity is audit_anchor
        ]

    # Controlled flexibility: strip broad blob-ish fields in Studio outputs.
    blob_like_fields = {"metadata", "meta", "permissions", "permission_json", "permissions_json", "config", "configuration", "condition"}
    for entity in entities:
        fields = entity.get("fields") if isinstance(entity.get("fields"), list) else []
        entity["fields"] = [
            field
            for field in (_normalize_field(item) for item in fields)
            if field and str(field.get("name") or "").strip().lower() not in blob_like_fields
        ]

    relationships_out = _dedupe_strings(
        [str(item).strip() for item in relationships if str(item).strip()]
        + (["Order 1..* OrderItem"] if order and order_item else [])
        + (["Product 1..* OrderItem"] if product and order_item else [])
        + (["Product 1..* ProductVariant"] if product and product_variant else [])
        + (["ProductVariant 1..* Inventory"] if product_variant and inventory else [])
        + (["Workflow 1..* Step"] if workflow and step else [])
        + (["User 1..* AuditLog"] if _find_entity_by_keys(entities, {"audit_log"}) else [])
    )

    # No over-fragmentation: if above studio range, trim weakest utility entities first.
    if len(entities) > 20:
        weak_keys = {"tag", "label", "note", "comment", "attachment", "setting", "preference", "helper", "mapping"}
        pruned = []
        for entity in entities:
            key = _to_snake_case(str(entity.get("name") or ""))
            if len(entities) - len(pruned) <= 20:
                break
            if key in weak_keys:
                pruned.append(key)
        if pruned:
            entities = [
                entity
                for entity in entities
                if _to_snake_case(str(entity.get("name") or "")) not in set(pruned)
            ]

    # Tier assignment metadata for Studio architecture mode.
    category_map: Dict[str, str] = {}
    for entity in entities:
        name = _to_snake_case(str(entity.get("name") or ""))
        if name in {"order", "product", "booking", "document", "user", "vendor", "customer", "inventory"}:
            category_map[str(entity.get("name") or name)] = "Core"
        elif name in {"workflow", "step", "product_variant", "variant", "folder", "collection"}:
            category_map[str(entity.get("name") or name)] = "Structural"
        elif name in {"order_item", "booking_slot", "cart_item", "payment", "settlement", "dispute", "invoice"}:
            category_map[str(entity.get("name") or name)] = "Transactional"
        else:
            category_map[str(entity.get("name") or name)] = "Supporting"

    blueprint["entities"] = _sanitize_schema_entities(_dedupe_entities(entities))
    blueprint["relationships"] = relationships_out
    meta = blueprint.get("__meta") if isinstance(blueprint.get("__meta"), dict) else {}
    meta["studio_entity_categories"] = category_map
    blueprint["__meta"] = meta
    return blueprint


def _apply_growth_billing_refinement(blueprint: Dict[str, Any], content: str) -> Dict[str, Any]:
    entities = blueprint.get("entities") if isinstance(blueprint.get("entities"), list) else []
    relationships = blueprint.get("relationships") if isinstance(blueprint.get("relationships"), list) else []
    if not entities:
        return blueprint

    original_count = len(entities)
    lowered = str(content or "").lower()

    def ensure_entity(name: str, fields: List[Dict[str, Any]]) -> Dict[str, Any]:
        return _add_entity_if_missing(entities, name, fields)

    ensure_entity(
        "Organization",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "name", "type": "text", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
    )
    ensure_entity(
        "User",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "organization_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "email", "type": "text", "constraints": ["not_null", "unique"]},
        ],
    )
    ensure_entity(
        "Role",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "name", "type": "text", "constraints": ["not_null", "unique"]},
        ],
    )
    ensure_entity(
        "Product",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "organization_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "name", "type": "text", "constraints": ["not_null"]},
        ],
    )
    ensure_entity(
        "Plan",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "product_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "name", "type": "text", "constraints": ["not_null"]},
        ],
    )
    subscription = ensure_entity(
        "Subscription",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "organization_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "plan_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
    )

    usage_event = ensure_entity(
        "UsageEvent",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "subscription_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "metric_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "quantity", "type": "numeric", "constraints": ["not_null"]},
            {"name": "occurred_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    usage_aggregate = ensure_entity(
        "UsageAggregate",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "subscription_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "billing_cycle_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "metric_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "total_quantity", "type": "numeric", "constraints": ["not_null"]},
        ],
    )

    billing_cycle = ensure_entity(
        "BillingCycle",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "subscription_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "period_start", "type": "timestamptz", "constraints": ["not_null"]},
            {"name": "period_end", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    invoice = ensure_entity(
        "Invoice",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "billing_cycle_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "total_amount", "type": "numeric", "constraints": ["not_null"]},
        ],
    )
    invoice_line = ensure_entity(
        "InvoiceLineItem",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "invoice_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "usage_aggregate_id", "type": "uuid", "constraints": ["foreign_key"]},
            {"name": "pricing_rule_id", "type": "uuid", "constraints": ["foreign_key"]},
            {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
        ],
    )

    account = ensure_entity(
        "BalanceAccount",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "organization_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "currency", "type": "text", "constraints": ["not_null"]},
        ],
    )
    transaction = ensure_entity(
        "Transaction",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "account_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "invoice_id", "type": "uuid", "constraints": ["foreign_key"]},
            {"name": "entry_type", "type": "text", "constraints": ["not_null"]},
            {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
            {"name": "posted_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    payment = ensure_entity(
        "Payment",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "invoice_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
        ],
    )
    payment_attempt = ensure_entity(
        "PaymentAttempt",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "payment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "attempt_number", "type": "integer", "constraints": ["not_null"]},
            {"name": "attempted_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    refund = ensure_entity(
        "Refund",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "payment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
        ],
    )

    pricing_rule = ensure_entity(
        "PricingRule",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "plan_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "rule_type", "type": "text", "constraints": ["not_null"]},
            {"name": "value", "type": "numeric", "constraints": []},
        ],
    )
    metric = ensure_entity(
        "MetricDefinition",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "code", "type": "text", "constraints": ["not_null", "unique"]},
            {"name": "unit", "type": "text", "constraints": ["not_null"]},
        ],
    )

    ensure_entity(
        "Notification",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "message", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    ensure_entity(
        "AuditLog",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "action_type", "type": "text", "constraints": ["not_null"]},
            {"name": "entity_type", "type": "text", "constraints": ["not_null"]},
            {"name": "entity_id", "type": "uuid", "constraints": ["not_null"]},
            {"name": "timestamp", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )

    # Enforce no shortcuts in subscription/invoice entities.
    for entity in entities:
        key = _to_snake_case(str(entity.get("name") or ""))
        fields = entity.get("fields") if isinstance(entity.get("fields"), list) else []
        if key == "subscription":
            entity["fields"] = [
                field for field in (_normalize_field(item) for item in fields)
                if field and str(field.get("name") or "").strip().lower() not in {"usage", "usage_count", "payment_id", "invoice_id", "amount_paid"}
            ]
            _ensure_field(entity, "status", "text", ["not_null"])
        if key == "invoice":
            entity["fields"] = [
                field for field in (_normalize_field(item) for item in fields)
                if field and str(field.get("name") or "").strip().lower() not in {"payment_status", "payment_id", "usage_total"}
            ]
            _ensure_field(entity, "status", "text", ["not_null"])
        if key == "payment":
            _ensure_field(entity, "status", "text", ["not_null"])

    relationships_out = _dedupe_strings(
        [str(item).strip() for item in relationships if str(item).strip()]
        + [
            "Subscription 1..* BillingCycle",
            "BillingCycle 1..* Invoice",
            "UsageEvent *..1 UsageAggregate",
            "UsageAggregate 1..* InvoiceLineItem",
            "Invoice 1..* InvoiceLineItem",
            "Invoice 1..* Payment",
            "Payment 1..* PaymentAttempt",
            "Invoice 1..* Transaction",
            "Payment 1..* Transaction",
            "Payment 1..* Refund",
            "BalanceAccount 1..* Transaction",
        ]
    )

    entities = _sanitize_schema_entities(_dedupe_entities(entities))
    if len(entities) > 30:
        weak = {"tag", "note", "comment", "label", "helper", "mapping", "setting", "preference"}
        entities = [entity for entity in entities if _to_snake_case(str(entity.get("name") or "")) not in weak][:30]
    if len(entities) < 18:
        ensure_entity(
            "CreditNote",
            [
                {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
                {"name": "invoice_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
                {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
            ],
        )
        entities = _sanitize_schema_entities(_dedupe_entities(entities))

    has_ledger = any(_to_snake_case(str(item.get("name") or "")) == "transaction" for item in entities)
    has_usage_agg = any(_to_snake_case(str(item.get("name") or "")) == "usage_aggregate" for item in entities)
    has_lifecycle = all(
        _find_entity_by_keys(entities, {key}) is not None
        for key in {"subscription", "invoice", "payment"}
    )
    under_specified = original_count < 18 or (not has_ledger) or (not has_usage_agg) or (not has_lifecycle)

    meta = blueprint.get("__meta") if isinstance(blueprint.get("__meta"), dict) else {}
    meta["growth_system_status"] = "UNDER-SPECIFIED" if under_specified else "SUFFICIENT"
    blueprint["__meta"] = meta
    blueprint["entities"] = entities
    blueprint["relationships"] = relationships_out
    return blueprint


def _apply_growth_orchestration_refinement(blueprint: Dict[str, Any], content: str) -> Dict[str, Any]:
    entities = blueprint.get("entities") if isinstance(blueprint.get("entities"), list) else []
    relationships = blueprint.get("relationships") if isinstance(blueprint.get("relationships"), list) else []
    if not entities:
        return blueprint

    lowered = str(content or "").lower()
    logistics_cues = ["shipment", "package", "delivery", "route", "warehouse", "driver", "logistics", "courier"]
    billing_cues = ["subscription", "invoice", "billing", "usage", "meter", "pricing", "ledger", "payment", "refund", "escrow"]
    if any(cue in lowered for cue in billing_cues):
        return _apply_growth_billing_refinement(blueprint, content)
    if not any(cue in lowered for cue in logistics_cues):
        blueprint["entities"] = _sanitize_schema_entities(_dedupe_entities(entities))
        blueprint["relationships"] = _dedupe_strings([str(item).strip() for item in relationships if str(item).strip()])
        return blueprint

    # Remove fake logic entities and duplicated role entities.
    fake_or_duplicate = {
        "fare_calculator",
        "calculator",
        "processor",
        "pricing_engine",
        "customer",
        "operator",
        "delivery_agent",
        "warehouse_staff",
    }
    entities = [
        entity
        for entity in entities
        if _to_snake_case(str(entity.get("name") or "")) not in fake_or_duplicate
        and not _to_snake_case(str(entity.get("name") or "")).endswith("_calculator")
        and not _to_snake_case(str(entity.get("name") or "")).endswith("_processor")
    ]

    shipment = _add_entity_if_missing(
        entities,
        "Shipment",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "order_ref", "type": "text", "constraints": ["unique"]},
            {"name": "origin_location", "type": "text", "constraints": ["not_null"]},
            {"name": "destination_location", "type": "text", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    package = _add_entity_if_missing(
        entities,
        "Package",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "shipment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "weight", "type": "numeric", "constraints": []},
            {"name": "dimensions", "type": "text", "constraints": []},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
    )

    user = _add_entity_if_missing(
        entities,
        "User",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "email", "type": "text", "constraints": ["not_null", "unique"]},
            {"name": "full_name", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    role = _add_entity_if_missing(
        entities,
        "Role",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "name", "type": "text", "constraints": ["not_null", "unique"]},
        ],
    )
    user_role = _add_entity_if_missing(
        entities,
        "UserRole",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "user_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "role_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "assigned_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )

    vehicle = _add_entity_if_missing(
        entities,
        "Vehicle",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "plate_number", "type": "text", "constraints": ["not_null", "unique"]},
            {"name": "capacity", "type": "numeric", "constraints": []},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
    )

    route = _add_entity_if_missing(
        entities,
        "Route",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "route_code", "type": "text", "constraints": ["unique"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
        ],
    )
    route_stop = _add_entity_if_missing(
        entities,
        "RouteStop",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "route_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "sequence_order", "type": "integer", "constraints": ["not_null"]},
            {"name": "location", "type": "text", "constraints": ["not_null"]},
            {"name": "shipment_id", "type": "uuid", "constraints": ["foreign_key"]},
        ],
    )

    shipment_assignment = _add_entity_if_missing(
        entities,
        "ShipmentAssignment",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "shipment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "driver_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "vehicle_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "route_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "assigned_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )

    route_assignment = _add_entity_if_missing(
        entities,
        "RouteAssignment",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "route_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "driver_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "vehicle_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "assigned_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )

    delivery_attempt = _add_entity_if_missing(
        entities,
        "DeliveryAttempt",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "shipment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "attempt_number", "type": "integer", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "timestamp", "type": "timestamptz", "constraints": ["not_null"]},
            {"name": "failure_reason", "type": "text", "constraints": []},
        ],
    )

    shipment_event = _add_entity_if_missing(
        entities,
        "ShipmentEvent",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "shipment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "location", "type": "text", "constraints": []},
            {"name": "timestamp", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )

    return_shipment = _add_entity_if_missing(
        entities,
        "ReturnShipment",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "shipment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "reason", "type": "text", "constraints": []},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    exception_issue = _add_entity_if_missing(
        entities,
        "ExceptionIssue",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "shipment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "type", "type": "text", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )

    warehouse = _add_entity_if_missing(
        entities,
        "Warehouse",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "name", "type": "text", "constraints": ["not_null"]},
            {"name": "location", "type": "text", "constraints": ["not_null"]},
        ],
    )
    warehouse_tx = _add_entity_if_missing(
        entities,
        "WarehouseTransaction",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "package_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "warehouse_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "action", "type": "text", "constraints": ["not_null"]},
            {"name": "timestamp", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )

    billing = _add_entity_if_missing(
        entities,
        "BillingRecord",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "shipment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "issued_at", "type": "timestamptz", "constraints": ["not_null"]},
        ],
    )
    payment = _add_entity_if_missing(
        entities,
        "Payment",
        [
            {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
            {"name": "billing_record_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
            {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
            {"name": "status", "type": "text", "constraints": ["not_null"]},
            {"name": "paid_at", "type": "timestamptz", "constraints": []},
        ],
    )
    if any(token in lowered for token in ["refund", "return", "cancel"]):
        _add_entity_if_missing(
            entities,
            "Refund",
            [
                {"name": "id", "type": "uuid", "constraints": ["primary_key"]},
                {"name": "payment_id", "type": "uuid", "constraints": ["foreign_key", "not_null"]},
                {"name": "amount", "type": "numeric", "constraints": ["not_null"]},
                {"name": "status", "type": "text", "constraints": ["not_null"]},
                {"name": "created_at", "type": "timestamptz", "constraints": ["not_null"]},
            ],
        )

    # Remove direct assignment FKs from Shipment.
    shipment_fields = shipment.get("fields") if isinstance(shipment.get("fields"), list) else []
    shipment["fields"] = [
        field
        for field in (_normalize_field(item) for item in shipment_fields)
        if field and str(field.get("name") or "").strip().lower() not in {"driver_id", "vehicle_id", "route_id"}
    ]

    relationships_out = _dedupe_strings(
        [str(item).strip() for item in relationships if str(item).strip()]
        + [
            "Shipment 1..* Package",
            "Shipment 1..* ShipmentAssignment",
            "Route 1..* RouteStop",
            "Route 1..* RouteAssignment",
            "Shipment 1..* DeliveryAttempt",
            "Shipment 1..* ShipmentEvent",
            "Shipment 1..* ReturnShipment",
            "Shipment 1..* ExceptionIssue",
            "Package 1..* WarehouseTransaction",
            "Warehouse 1..* WarehouseTransaction",
            "Shipment 1..* BillingRecord",
            "BillingRecord 1..* Payment",
            "User 1..* UserRole",
            "Role 1..* UserRole",
        ]
    )

    # Growth target: keep 18-30 meaningful entities.
    entities = _sanitize_schema_entities(_dedupe_entities(entities))
    if len(entities) > 30:
        weak = {"note", "comment", "tag", "label", "helper", "mapping", "setting", "preference"}
        entities = [
            entity
            for entity in entities
            if _to_snake_case(str(entity.get("name") or "")) not in weak
        ][:30]

    category_map: Dict[str, str] = {}
    for entity in entities:
        key = _to_snake_case(str(entity.get("name") or ""))
        if key in {"shipment", "package", "user", "vehicle", "warehouse"}:
            category_map[str(entity.get("name") or key)] = "Core"
        elif key in {"route", "route_stop", "shipment_assignment", "route_assignment", "role", "user_role"}:
            category_map[str(entity.get("name") or key)] = "Structural"
        elif key in {"delivery_attempt", "shipment_event", "warehouse_transaction", "return_shipment", "exception_issue"}:
            category_map[str(entity.get("name") or key)] = "Transactional"
        elif key in {"billing_record", "payment", "refund", "invoice"}:
            category_map[str(entity.get("name") or key)] = "Financial"
        else:
            category_map[str(entity.get("name") or key)] = "Supporting"

    blueprint["entities"] = entities
    blueprint["relationships"] = relationships_out
    meta = blueprint.get("__meta") if isinstance(blueprint.get("__meta"), dict) else {}
    meta["growth_entity_categories"] = category_map
    blueprint["__meta"] = meta
    return blueprint


def _apply_creator_mvp_refinement(blueprint: Dict[str, Any], content: str) -> Dict[str, Any]:
    entities = blueprint.get("entities") if isinstance(blueprint.get("entities"), list) else []
    if not entities:
        return blueprint

    entities = _sanitize_schema_entities(entities)
    entities = _normalize_creator_role_entities(entities)

    by_name: Dict[str, Dict[str, Any]] = {}
    for item in entities:
        if not isinstance(item, dict):
            continue
        name = str(item.get("name") or "").strip()
        if not name:
            continue
        by_name[_to_snake_case(name)] = item

    creator_domain = _detect_creator_domain(content, entities)

    task = by_name.get("task")
    if task:
        _ensure_field(task, "parent_task_id", "uuid", ["foreign_key"])

    review = by_name.get("review")
    if review:
        _ensure_field(review, "reviewer_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(review, "task_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(review, "decision", "text", ["not_null"])
        _ensure_field(review, "feedback", "text", [])

    dependency = by_name.get("dependency")
    if dependency:
        _ensure_field(dependency, "task_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(dependency, "depends_on_task_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(dependency, "type", "text", ["not_null"])

    content_lower = str(content or "").lower()
    is_expense_domain = "expense" in content_lower and ("group" in content_lower or "split" in content_lower)
    is_file_domain = creator_domain == "file_sharing"

    split = by_name.get("split")
    expense_split = by_name.get("expense_split")
    if split and not expense_split and is_expense_domain:
        split["name"] = "ExpenseSplit"
        expense_split = split
        by_name["expense_split"] = split

    if expense_split:
        _ensure_field(expense_split, "expense_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(expense_split, "user_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(expense_split, "share_amount", "numeric", ["not_null"])
        _ensure_field(expense_split, "share_ratio", "numeric", [])

    settlement = by_name.get("settlement")
    if settlement:
        fields = settlement.get("fields") if isinstance(settlement.get("fields"), list) else []
        settlement["fields"] = [
            field
            for field in (_normalize_field(item) for item in fields)
            if field and str(field.get("name", "")).strip().lower() != "expense_id"
        ]
        _ensure_field(settlement, "group_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(settlement, "from_user_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(settlement, "to_user_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(settlement, "amount", "numeric", ["not_null"])

    if is_expense_domain and by_name.get("balance"):
        persistence_cues = ["persisted balance", "balance snapshot", "materialized balance", "balance history"]
        keep_balance = any(cue in content_lower for cue in persistence_cues)
        if not keep_balance:
            entities = [
                entity
                for entity in entities
                if _to_snake_case(str(entity.get("name") or "")) != "balance"
            ]
            by_name.pop("balance", None)

    if is_expense_domain and by_name.get("transaction") and by_name.get("expense") and by_name.get("settlement"):
        entities = [
            entity
            for entity in entities
            if _to_snake_case(str(entity.get("name") or "")) != "transaction"
        ]
        by_name.pop("transaction", None)

    if is_file_domain:
        unrelated_for_file = {
            "expense",
            "split",
            "expense_split",
            "settlement",
            "balance",
            "group",
            "group_member",
            "transaction",
            "loan",
            "payment",
        }
        entities = [
            entity
            for entity in entities
            if _to_snake_case(str(entity.get("name") or "")) not in unrelated_for_file
        ]
        by_name = {
            _to_snake_case(str(item.get("name") or "")): item
            for item in entities
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }

        share = by_name.get("share")
        permission = by_name.get("permission")
        if share:
            _ensure_field(share, "id", "uuid", ["primary_key"])
            _ensure_field(share, "file_id", "uuid", ["foreign_key", "not_null"])
            _ensure_field(share, "owner_user_id", "uuid", ["foreign_key", "not_null"])
            _ensure_field(share, "target_user_id", "uuid", ["foreign_key"])
            _ensure_field(share, "permission_type", "text", ["not_null"])
            _ensure_field(share, "is_public", "boolean", ["default_false"])
            _ensure_field(share, "public_token", "text", ["unique"])

        if permission and share:
            permission_fields = permission.get("fields") if isinstance(permission.get("fields"), list) else []
            for field in permission_fields:
                normalized = _normalize_field(field)
                if not normalized:
                    continue
                field_name = str(normalized.get("name") or "").strip().lower()
                if field_name in {"permission_type", "target_user_id", "owner_user_id", "file_id"}:
                    _ensure_field(share, field_name, str(normalized.get("type") or "text"), normalized.get("constraints") or [])
            entities = [
                entity
                for entity in entities
                if _to_snake_case(str(entity.get("name") or "")) != "permission"
            ]

        folder = next((item for item in entities if _to_snake_case(str(item.get("name") or "")) == "folder"), None)
        if folder:
            fields = folder.get("fields") if isinstance(folder.get("fields"), list) else []
            folder["fields"] = [
                field
                for field in (_normalize_field(item) for item in fields)
                if field and str(field.get("name") or "").strip().lower() not in {"permissions", "permissions_json", "access_rules"}
            ]
            _ensure_field(folder, "owner_user_id", "uuid", ["foreign_key", "not_null"])
            _ensure_field(folder, "parent_folder_id", "uuid", ["foreign_key"])

        version = next((item for item in entities if _to_snake_case(str(item.get("name") or "")) == "version"), None)
        if version:
            fields = version.get("fields") if isinstance(version.get("fields"), list) else []
            version["fields"] = [
                field
                for field in (_normalize_field(item) for item in fields)
                if field and str(field.get("name") or "").strip().lower() != "folder_id"
            ]
            _ensure_field(version, "file_id", "uuid", ["foreign_key", "not_null"])
            _ensure_field(version, "version_number", "integer", ["not_null"])

        activity = next(
            (
                item
                for item in entities
                if _to_snake_case(str(item.get("name") or "")) in {"activity", "activity_log"}
            ),
            None,
        )
        if activity:
            _ensure_field(activity, "action_type", "text", ["not_null"])
            _ensure_field(activity, "entity_type", "text", ["not_null"])
            _ensure_field(activity, "entity_id", "uuid", ["not_null"])

        core_keys = {"user", "file", "folder", "share", "version", "activity", "activity_log"}
        for key in core_keys:
            if key in by_name:
                continue
            label = "ActivityLog" if key == "activity_log" else key.title()
            entities.append({"name": label, "fields": _default_fields_for_entity(label)})

        by_name = {
            _to_snake_case(str(item.get("name") or "")): item
            for item in entities
            if isinstance(item, dict) and str(item.get("name") or "").strip()
        }

    notification = by_name.get("notification")
    if notification:
        fields = notification.get("fields") if isinstance(notification.get("fields"), list) else []
        sanitized_fields = []
        for field in fields:
            normalized = _normalize_field(field)
            if not normalized:
                continue
            if str(normalized.get("name", "")).strip().lower() == "loan_id":
                continue
            sanitized_fields.append(normalized)
        notification["fields"] = sanitized_fields
        _ensure_field(notification, "user_id", "uuid", ["foreign_key", "not_null"])
        _ensure_field(notification, "task_id", "uuid", ["foreign_key"])
        _ensure_field(notification, "message", "text", ["not_null"])

    relationships = blueprint.get("relationships") if isinstance(blueprint.get("relationships"), list) else []
    normalized_relationships = [str(item).strip() for item in relationships if str(item).strip()]

    if task and review:
        normalized_relationships.append("Task 1..* Review")
        normalized_relationships.append("User 1..* Review")
    if task and dependency:
        normalized_relationships.append("Task 1..* Dependency")
        normalized_relationships.append("Dependency *..1 Task")
    if task and notification:
        normalized_relationships.append("Task 1..* Notification")
        normalized_relationships.append("User 1..* Notification")
    if is_expense_domain:
        if by_name.get("group_member"):
            normalized_relationships.append("Group 1..* GroupMember")
            normalized_relationships.append("User 1..* GroupMember")
        if by_name.get("expense") and by_name.get("expense_split"):
            normalized_relationships.append("Expense 1..* ExpenseSplit")
            normalized_relationships.append("User 1..* ExpenseSplit")
        if by_name.get("group") and by_name.get("settlement"):
            normalized_relationships.append("Group 1..* Settlement")
            normalized_relationships.append("User 1..* Settlement")
    if is_file_domain:
        if by_name.get("user") and by_name.get("folder"):
            normalized_relationships.append("User 1..* Folder")
        if by_name.get("folder") and by_name.get("file"):
            normalized_relationships.append("Folder 1..* File")
        if by_name.get("file") and by_name.get("share"):
            normalized_relationships.append("File 1..* Share")
            normalized_relationships.append("User 1..* Share")
        if by_name.get("file") and by_name.get("version"):
            normalized_relationships.append("File 1..* Version")
        if by_name.get("user") and (by_name.get("activity") or by_name.get("activity_log")):
            normalized_relationships.append("User 1..* ActivityLog")

    if is_file_domain:
        entities, normalized_relationships = _apply_creator_file_precision(entities, normalized_relationships)

    blueprint["relationships"] = _dedupe_strings(normalized_relationships)
    blueprint["entities"] = _ensure_entity_field_depth(_sanitize_schema_entities(_dedupe_entities(entities)), content)

    if is_file_domain:
        # Ensure creator precision survives default-field expansion step.
        refined_entities, refined_relationships = _apply_creator_file_precision(
            blueprint.get("entities") if isinstance(blueprint.get("entities"), list) else [],
            blueprint.get("relationships") if isinstance(blueprint.get("relationships"), list) else [],
        )
        blueprint["entities"] = _sanitize_schema_entities(_dedupe_entities(refined_entities))
        blueprint["relationships"] = _dedupe_strings(refined_relationships)

    return blueprint


def build_blueprint(content: str, plan_code: str | None = None) -> Dict:
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
                raw = _call_groq_for_blueprint(
                    content if not warning else f"{content}\n\n{warning}",
                    model=model,
                    plan_code=plan_code,
                )
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
            entities = _ensure_entity_field_depth(entities, content)
            entities = _inject_fintech_domain_fields(content, entities)
            entities = _align_entity_field_types(entities)
            entities = _sanitize_schema_entities(entities)
            _log_field_richness_warning(entities, content)
            blueprint["entities"] = entities
            relationships = blueprint.get("relationships", [])
            rules = blueprint.get("rules", [])

            rel_output = _generate_relationships_and_join_tables(content, entities, model=model)
            blueprint["relationships"] = rel_output.get("relationships", [])
            blueprint["join_tables"] = _ensure_join_table_minimum_fields(rel_output.get("join_tables", []))
            relationships = blueprint.get("relationships", [])
            join_tables = blueprint.get("join_tables", [])
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
                migration_sql = _generate_migration_sql_batched(entities, relationships, join_tables, model=model)
                if migration_sql:
                    reconciled_sql = _reconcile_migration_sql(migration_sql, entities, join_tables)
                    blueprint["migration_sql"] = _normalize_create_table_defaults(reconciled_sql)
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

            if str(plan_code or "").strip().lower() == "creator":
                blueprint = _apply_creator_mvp_refinement(blueprint, content)
            if str(plan_code or "").strip().lower() == "studio":
                blueprint = _apply_studio_depth_refinement(blueprint, content)
            if str(plan_code or "").strip().lower() == "growth":
                blueprint = _apply_growth_orchestration_refinement(blueprint, content)

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
    fallback["entities"] = _sanitize_schema_entities(fallback.get("entities") or [])
    if str(plan_code or "").strip().lower() == "creator":
        fallback = _apply_creator_mvp_refinement(fallback, content)
    if str(plan_code or "").strip().lower() == "studio":
        fallback = _apply_studio_depth_refinement(fallback, content)
    if str(plan_code or "").strip().lower() == "growth":
        fallback = _apply_growth_orchestration_refinement(fallback, content)
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
