"""
Scaffold generator: turns a GeneratedArchitectureSpec (pydantic model or its dict form)
into a project that actually builds and boots.

Everything here takes plain dicts so it works both at generation time
(spec.model_dump()) and at download time (the stored JSON result).
"""
import json
import keyword
import re
import secrets
from typing import Any, Dict, List, Optional, Tuple

# Stored runs carrying another version are regenerated when downloaded.
SCAFFOLD_VERSION = 3

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def as_dict(spec: Any) -> Dict[str, Any]:
    return spec.model_dump(mode="json") if hasattr(spec, "model_dump") else spec


def pascal_case(name: str) -> str:
    out = "".join(p[:1].upper() + p[1:] for p in re.split(r"[^0-9a-zA-Z]+", name) if p)
    if not out:
        out = "Entity"
    return f"E{out}" if out[0].isdigit() else out


def camel_case(name: str) -> str:
    parts = [p for p in re.split(r"[^0-9a-zA-Z]+", name) if p]
    if not parts:
        return "handler"
    out = parts[0][:1].lower() + parts[0][1:] + "".join(p[:1].upper() + p[1:] for p in parts[1:])
    return f"h{out[0].upper()}{out[1:]}" if out[0].isdigit() else out


def snake_case(name: str) -> str:
    out = re.sub(r"[^0-9a-zA-Z]+", "_", name).strip("_").lower()
    if not out:
        return "endpoint"
    return f"endpoint_{out}" if out[0].isdigit() else out


def q(ident: str) -> str:
    """Quote a SQL identifier (keeps reserved words like ORDER / USER valid)."""
    return '"' + ident.replace('"', '""') + '"'


def _unique(name: str, seen: set) -> str:
    base, n = name, 2
    while name in seen:
        name, n = f"{base}{n}", n + 1
    seen.add(name)
    return name


def _resolve_table(ref: str, names: List[str]) -> Optional[str]:
    """Match an FK target like 'Order' / 'orders' to a real table name."""
    if not ref:
        return None
    lowered = {n.lower(): n for n in names}
    r = ref.lower()
    candidates = [r, r + "s", r + "es", r[:-1] if r.endswith("s") else r,
                  r[:-3] + "y" if r.endswith("ies") else r,
                  r[:-1] + "ies" if r.endswith("y") else r]
    for c in candidates:
        if c in lowered:
            return lowered[c]
    return None


def _fk_parts(col: Dict[str, Any], table_names: List[str]) -> Optional[Tuple[str, str]]:
    fk = col.get("foreign_key")
    if not fk:
        return None
    tbl, _, c = fk.partition(".")
    target = _resolve_table(tbl.strip(), table_names)
    return (target, (c.strip() or "id")) if target else None


# ---------------------------------------------------------------------------
# Column typing (single source of truth for SQL + entities + models)
# ---------------------------------------------------------------------------

_MONEY_NAMES = re.compile(r"(^|_)(price|amount|total|subtotal|tax|fee|cost|balance|earnings)($|_)")
_GEO_NAMES = re.compile(r"(^|_)(lat|lng|lon|latitude|longitude)($|_)")


def column_kind(col: Dict[str, Any]) -> str:
    """Returns one of: uuid int bigint numeric float bool timestamp date json text enum string."""
    t = (col.get("type") or "").strip().lower()
    name = (col.get("name") or "").lower()
    if col.get("enum_values") or t == "enum":
        return "enum"
    if "uuid" in t:
        return "uuid"
    if t in ("bigint", "biginteger", "long"):
        return "bigint"
    if t in ("int", "integer", "smallint", "serial", "number") or t.startswith("int"):
        return "int"
    if t in ("numeric", "decimal", "money"):
        return "float" if _GEO_NAMES.search(name) else "numeric"
    if t in ("float", "double", "real", "double precision"):
        return "float"
    if "bool" in t:
        return "bool"
    if t == "date":
        return "date"
    if t in ("datetime", "timestamp", "timestamptz", "time") or "timestamp" in t or "datetime" in t:
        return "timestamp"
    if "json" in t:
        return "json"
    if t == "text":
        return "text"
    # Untyped/string columns the LLM clearly meant as numbers
    if _GEO_NAMES.search(name):
        return "float"
    if _MONEY_NAMES.search(name) and t in ("string", "varchar", ""):
        return "numeric"
    return "string"


_SQL_TYPES = {
    "uuid": "UUID", "int": "INTEGER", "bigint": "BIGINT", "numeric": "NUMERIC(12,2)",
    "float": "DOUBLE PRECISION", "bool": "BOOLEAN", "timestamp": "TIMESTAMP", "date": "DATE",
    "json": "JSONB", "text": "TEXT", "enum": "VARCHAR(50)", "string": "VARCHAR(255)",
}


_COUNTER_NAMES = re.compile(r"(^|_)(count|counts|rating|attempts|deliveries|orders|reviews|balance|earnings)($|_)")


def _sql_default(col: Dict[str, Any], kind: str) -> str:
    name = (col.get("name") or "").lower()
    if col.get("is_primary_key") and kind == "uuid":
        return "DEFAULT gen_random_uuid()"
    if kind == "timestamp" and name in ("created_at", "updated_at"):
        return "DEFAULT now()"
    if kind == "bool" and name in ("is_active", "is_available", "is_enabled"):
        return "DEFAULT TRUE"
    if kind == "bool" and name.startswith("is_"):
        return "DEFAULT FALSE"
    required = not col.get("is_nullable") and not col.get("is_primary_key") and not col.get("foreign_key")
    if kind == "enum" and required and col.get("enum_values"):
        return "DEFAULT '" + str(col["enum_values"][0]).replace("'", "''") + "'"  # initial state
    if kind in ("int", "bigint", "numeric", "float") and required and _COUNTER_NAMES.search(name):
        return "DEFAULT 0"
    return ""


# ---------------------------------------------------------------------------
# SQL migration
# ---------------------------------------------------------------------------

def _creation_order(tables: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    names = [t["name"] for t in tables]
    deps = {}
    for t in tables:
        d = set()
        for c in t["columns"]:
            fk = _fk_parts(c, names)
            if fk and fk[0] != t["name"]:
                d.add(fk[0])
        deps[t["name"]] = d
    ordered, placed = [], set()
    remaining = list(tables)
    while remaining:
        ready = [t for t in remaining if deps[t["name"]] <= placed]
        if not ready:  # circular — place the first, FKs to unplaced tables get deferred
            ready = [remaining[0]]
        for t in ready:
            ordered.append(t)
            placed.add(t["name"])
            remaining.remove(t)
    return ordered


def generate_migration_sql(spec: Any) -> str:
    spec = as_dict(spec)
    tables = spec["database"]["tables"]
    names = [t["name"] for t in tables]
    sql = ["-- DB migration script generated by Baxel", "-- Idempotent: safe to run on every start.\n"]
    created: set = set()
    deferred: List[str] = []

    for t in _creation_order(tables):
        lines = []
        pk_cols = [c for c in t["columns"] if c.get("is_primary_key")]
        for c in t["columns"]:
            kind = column_kind(c)
            parts = [q(c["name"]), _SQL_TYPES[kind]]
            if c.get("is_primary_key") and len(pk_cols) == 1:
                parts.append("PRIMARY KEY")
            elif not c.get("is_nullable") or c.get("is_primary_key"):
                parts.append("NOT NULL")
            # Login identities must be unique (accounts = tables that store a password hash)
            if (c["name"].lower() in ("email", "username") and not c.get("is_primary_key")
                    and any(x["name"] == "password_hash" for x in t["columns"])):
                parts.append("UNIQUE")
            default = _sql_default(c, kind)
            if default:
                parts.append(default)
            fk = _fk_parts(c, names)
            if fk:
                target, tcol = fk
                if target == t["name"] or target in created:
                    parts.append(f"REFERENCES {q(target)}({q(tcol)})")
                else:
                    cname = f"fk_{t['name']}_{c['name']}"[:60]
                    deferred.append(
                        "DO $$ BEGIN\n"
                        f"  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = '{cname}') THEN\n"
                        f"    ALTER TABLE {q(t['name'])} ADD CONSTRAINT {q(cname)} "
                        f"FOREIGN KEY ({q(c['name'])}) REFERENCES {q(target)}({q(tcol)});\n"
                        "  END IF;\nEND $$;"
                    )
            if c.get("enum_values"):
                vals = ", ".join("'" + str(v).replace("'", "''") + "'" for v in c["enum_values"])
                parts.append(f"CHECK ({q(c['name'])} IN ({vals}))")
            lines.append("  " + " ".join(parts))
        if len(pk_cols) > 1:
            lines.append("  PRIMARY KEY (" + ", ".join(q(c["name"]) for c in pk_cols) + ")")
        sql.append(f"CREATE TABLE IF NOT EXISTS {q(t['name'])} (\n" + ",\n".join(lines) + "\n);\n")
        created.add(t["name"])

    if deferred:
        sql.append("-- Foreign keys that close circular references")
        sql.extend(d + "\n" for d in deferred)
    return "\n".join(sql)


# ---------------------------------------------------------------------------
# Endpoints (shared normalisation)
# ---------------------------------------------------------------------------

_PARAM_RE = re.compile(r"\{([^}/]+)\}|<([^>/]+)>|:([A-Za-z_][A-Za-z0-9_]*)")


def _path_params(path: str) -> List[str]:
    return [next(g for g in m.groups() if g) for m in _PARAM_RE.finditer(path)]


def _normalise_endpoints(endpoints: List[Dict[str, Any]], strip_api_prefix: bool):
    """Dedupes (method, path), orders literal segments before :params, picks unique handler names."""
    seen_routes, items = set(), []
    for ep in endpoints:
        method = (ep.get("method") or "GET").upper()
        path = "/" + (ep.get("path") or "/").strip("/")
        path = _PARAM_RE.sub(lambda m: "{" + next(g for g in m.groups() if g) + "}", path)
        if strip_api_prefix and (path == "/api" or path.startswith("/api/")):
            path = path[4:] or "/"
        key = (method, path)
        if key in seen_routes:
            continue
        seen_routes.add(key)
        items.append({**ep, "method": method, "path": path, "params": _path_params(path)})

    def sort_key(it):
        return tuple(1 if seg.startswith("{") else 0 for seg in it["path"].strip("/").split("/"))

    items.sort(key=sort_key)  # stable: literal segments (e.g. /available) before /{id}
    return items


# ---------------------------------------------------------------------------
# TypeScript / NestJS
# ---------------------------------------------------------------------------

_TS_TYPES = {"uuid": "string", "int": "number", "bigint": "string", "numeric": "number", "float": "number",
             "bool": "boolean", "timestamp": "Date", "date": "string", "json": "any", "text": "string",
             "enum": "string", "string": "string"}


def _ts_prop(name: str) -> str:
    return name if re.fullmatch(r"[A-Za-z_$][A-Za-z0-9_$]*", name) else json.dumps(name)


def class_names(spec: Any) -> Dict[str, str]:
    """table name -> unique entity class name (shared by entities and controller)."""
    seen: set = set()
    return {t["name"]: _unique(pascal_case(t["name"]), seen) for t in as_dict(spec)["database"]["tables"]}


def generate_ts_entities(spec: Any) -> Tuple[str, List[str]]:
    spec = as_dict(spec)
    names = [t["name"] for t in spec["database"]["tables"]]
    cls_map = class_names(spec)
    code = [
        "// TypeORM entities generated by Baxel",
        "import { Entity, PrimaryColumn, PrimaryGeneratedColumn, Column } from 'typeorm';\n",
        "// Postgres returns NUMERIC as string — convert so entities expose real numbers.",
        "const numeric = {",
        "  to: (v?: number | null) => v,",
        "  from: (v?: string | null) => (v === null || v === undefined ? v : parseFloat(v)),",
        "};\n",
    ]
    classes: List[str] = []
    for t in spec["database"]["tables"]:
        cls = cls_map[t["name"]]
        classes.append(cls)
        code.append(f"@Entity({json.dumps(t['name'])})")
        code.append(f"export class {cls} {{")
        if t.get("description"):
            code.append(f"  // {t['description']}\n")
        pk_cols = [c for c in t["columns"] if c.get("is_primary_key")]
        for c in t["columns"]:
            kind = column_kind(c)
            nullable = bool(c.get("is_nullable")) and not c.get("is_primary_key")
            ts_type = _TS_TYPES[kind]
            if kind == "enum" and c.get("enum_values"):
                ts_type = " | ".join(json.dumps(str(v)) for v in c["enum_values"])
            opts: List[str] = []
            if kind == "uuid":
                col_type = "'uuid'"
            elif kind == "int":
                col_type = "'int'"
            elif kind == "bigint":
                col_type = "'bigint'"
            elif kind == "numeric":
                col_type = "'numeric'"
                opts += ["precision: 12", "scale: 2", "transformer: numeric"]
            elif kind == "float":
                col_type = "'double precision'"
            elif kind == "bool":
                col_type = "'boolean'"
            elif kind == "timestamp":
                col_type = "'timestamp'"
            elif kind == "date":
                col_type = "'date'"
            elif kind == "json":
                col_type = "'jsonb'"
            elif kind == "text":
                col_type = "'text'"
            elif kind == "enum":
                col_type = "'varchar'"
                opts.append("length: 50")
            else:
                col_type = "'varchar'"
                opts.append("length: 255")
            if nullable:
                opts.append("nullable: true")
            default = _sql_default(c, kind)
            if kind == "timestamp" and default:
                opts.append("default: () => 'now()'")
            elif kind == "bool" and default:
                opts.append(f"default: {'true' if 'TRUE' in default else 'false'}")
            opt_str = (", { " + ", ".join(opts) + " }") if opts else ""
            if c.get("is_primary_key") and kind == "uuid" and len(pk_cols) == 1:
                deco = "@PrimaryGeneratedColumn('uuid')"
            elif c.get("is_primary_key"):
                deco = f"@PrimaryColumn({col_type}{opt_str})"
            else:
                deco = f"@Column({col_type}{opt_str})"
            fk = _fk_parts(c, names)
            note = f"  // FK -> {fk[0]}.{fk[1]}" if fk else ""
            code.append(f"  {deco}{note}")
            code.append(f"  {_ts_prop(c['name'])}: {ts_type}{' | null' if nullable else ''};\n")
        code.append("}\n")
    code.append("export const entities = [" + ", ".join(classes) + "];\n")
    return "\n".join(code), classes


# ---- Handler planning: infer what an endpoint does from its route ----------

def _singular(word: str) -> str:
    w = word.lower()
    if w.endswith("ies"):
        return w[:-3] + "y"
    if w.endswith(("ses", "xes")):
        return w[:-2]
    if w.endswith("s") and not w.endswith("ss"):
        return w[:-1]
    return w


def _norm(word: str) -> str:
    return re.sub(r"[^a-z0-9]", "", word.lower())


def _fuzzy_table(seg: str, names: List[str]) -> Optional[str]:
    exact = _resolve_table(seg.replace("-", "_"), names)
    if exact:
        return exact
    n = _norm(seg)
    sing = _singular(n)
    cands = [t for t in names if _norm(t) in (n, sing, sing + "s")]
    if len(cands) == 1:
        return cands[0]
    if len(sing) >= 4:
        cands = [t for t in names if _norm(t).startswith(sing) or _norm(t).endswith(sing)]
        if len(cands) == 1:
            return cands[0]
    return None


def _parse_steps(path: str) -> Optional[List[Dict[str, Any]]]:
    steps: List[Dict[str, Any]] = []
    for seg in path.strip("/").split("/"):
        if not seg or re.fullmatch(r"v\d+", seg):
            continue
        if seg.startswith("{"):
            if not steps or steps[-1]["id"] is not None:
                return None
            steps[-1]["id"] = ("param", seg[1:-1])
        elif seg == "me":
            if not steps or steps[-1]["id"] is not None:
                return None
            steps[-1]["id"] = ("me", None)
        else:
            steps.append({"res": seg, "id": None})
    return steps or None


class _Ctx:
    def __init__(self, spec: Dict[str, Any]):
        tables = spec["database"]["tables"]
        self.names = [t["name"] for t in tables]
        self.cls = class_names(spec)
        self.user_tables = [t["name"] for t in tables if any(c["name"] == "password_hash" for c in t["columns"])]
        self.cols = {t["name"]: {c["name"] for c in t["columns"]} for t in tables}
        self.fks: Dict[str, Dict[str, str]] = {}
        for t in tables:
            self.fks[t["name"]] = {}
            for c in t["columns"]:
                fk = _fk_parts(c, self.names)
                if fk:
                    self.fks[t["name"]][c["name"]] = fk[0]


_PERSON_COLUMNS = {"email", "phone", "phone_number", "full_name", "first_name", "last_name"}


def _user_table_for(text: str, ctx: _Ctx) -> Optional[str]:
    """Which account table does this auth endpoint belong to? None if it's a person type without credentials."""
    if not ctx.user_tables:
        return None
    n = _norm(text)
    for t in ctx.user_tables:
        if _singular(_norm(t)) in n:
            return t
    for t in ctx.names:
        if t not in ctx.user_tables and ctx.cols[t] & _PERSON_COLUMNS and _singular(_norm(t)) in n:
            return None  # e.g. "Register a courier" when couriers have no password column
    return ctx.user_tables[0]


def _plan_auth(ep: Dict[str, Any], ctx: _Ctx) -> Optional[Dict[str, Any]]:
    if ep["method"] != "POST" or not ctx.user_tables:
        return None
    text = f"{ep['path']} {ep.get('summary') or ''}".lower()
    kind = None
    if "refresh" in text:
        return {"op": "refresh", "table": None, "protected": False}
    if re.search(r"log.?in|sign.?in|authenticat", text) or ep["path"].rstrip("/").endswith("/token"):
        kind = "login"
    elif re.search(r"regist|sign.?up", text):
        kind = "register"
    else:
        steps = _parse_steps(ep["path"])
        # Creating an account always needs the password hashed, even behind an admin guard.
        if (steps and len(steps) == 1 and steps[0]["id"] is None
                and _fuzzy_table(steps[0]["res"], ctx.names) in ctx.user_tables):
            kind = "register"
    if not kind:
        return None
    table = _user_table_for(text, ctx)
    return {"op": kind, "table": table, "protected": False} if table else None


def _plan_crud(ep: Dict[str, Any], ctx: _Ctx) -> Optional[Dict[str, Any]]:
    steps = _parse_steps(ep["path"])
    if not steps or len(steps) > 2:
        return None
    tables = [_fuzzy_table(st["res"], ctx.names) for st in steps]
    if any(t is None for t in tables):
        return None
    method, protected = ep["method"], bool(ep.get("is_protected"))
    last, T = steps[-1], tables[-1]
    where: List[Tuple[str, Tuple[str, Optional[str]]]] = []
    asserts: List[Tuple[str, ...]] = []

    if len(steps) == 2:
        parent, PT = steps[-2], tables[-2]
        if parent["id"] is None:
            return None
        fk_cols = [c for c, tgt in ctx.fks[T].items() if tgt == PT]
        if not fk_cols:
            return None
        if parent["id"][0] == "me":
            if PT not in ctx.user_tables or not protected:
                return None
            asserts.append(("kind", PT))
            where.append((fk_cols[0], ("user", None)))
        else:
            where.append((fk_cols[0], ("param", parent["id"][1])))

    if last["id"]:
        kind, name = last["id"]
        if kind == "me":
            if T not in ctx.user_tables or not protected:
                return None
            asserts.append(("kind", T))
            where.append(("id", ("user", None)))
        else:
            if T in ctx.user_tables and protected:
                asserts.append(("self", T, name))
            where.append(("id", ("param", name)))

    # Rows owned by an account: scope to the caller when the token belongs to that account type
    owner = None
    if protected and T not in ctx.user_tables:
        for col, tgt in ctx.fks[T].items():
            if tgt in ctx.user_tables and col not in dict(where):
                owner = (col, tgt)
                break

    if method == "GET":
        op = "get" if last["id"] else "list"
    elif method == "POST" and not last["id"]:
        op = "create"
    elif method in ("PATCH", "PUT") and last["id"]:
        op = "update"
    elif method == "DELETE" and last["id"]:
        op = "remove"
    else:
        return None
    return {"op": op, "table": T, "where": where, "asserts": asserts, "owner": owner, "protected": protected}


def _plan(ep: Dict[str, Any], ctx: _Ctx) -> Optional[Dict[str, Any]]:
    return _plan_auth(ep, ctx) or _plan_crud(ep, ctx)


def _render_ts(plan: Optional[Dict[str, Any]], ctx: _Ctx) -> Optional[Dict[str, Any]]:
    if not plan:
        return None
    op = plan["op"]
    if op == "refresh":
        return {"lines": ["return this.auth.refresh(body);"], "classes": set(), "req": False}
    cls = ctx.cls[plan["table"]]
    if op in ("login", "register"):
        return {"lines": [f"return this.auth.{op}({cls}, {json.dumps(plan['table'])}, body);"],
                "classes": {cls}, "req": False}

    def expr(e):
        return "req.user.sub" if e[0] == "user" else camel_case(e[1])

    lines: List[str] = []
    for a in plan["asserts"]:
        if a[0] == "kind":
            lines.append(f"this.crud.assertKind(req.user, {json.dumps(a[1])});")
        else:
            lines.append(f"this.crud.assertSelf(req.user, {json.dumps(a[1])}, {camel_case(a[2])});")
    w = "{ " + ", ".join(f"{c}: {expr(e)}" for c, e in plan["where"]) + " }" if plan["where"] else "{}"
    user = "req.user" if plan["protected"] else "undefined"
    o = f", owner: {{ col: {json.dumps(plan['owner'][0])}, kind: {json.dumps(plan['owner'][1])} }}" if plan["owner"] else ""
    call = {
        "list": f"return this.crud.list({cls}, {{ where: {w}{o}, user: {user}, query }});",
        "get": f"return this.crud.get({cls}, {{ where: {w}{o}, user: {user} }});",
        "create": f"return this.crud.create({cls}, body, {{ set: {w}{o}, user: {user} }});",
        "update": f"return this.crud.update({cls}, body, {{ where: {w}{o}, user: {user} }});",
        "remove": f"return this.crud.remove({cls}, {{ where: {w}{o}, user: {user} }});",
    }[op]
    return {"lines": lines + [call], "classes": {cls}, "req": plan["protected"]}


def generate_ts_controller(spec: Any) -> str:
    spec = as_dict(spec)
    ctx = _Ctx(spec)
    eps = _normalise_endpoints(spec.get("endpoints", []), strip_api_prefix=True)
    method_map = {"GET": "Get", "POST": "Post", "PATCH": "Patch", "PUT": "Put", "DELETE": "Delete"}

    plans = [(ep, _render_ts(_plan(ep, ctx), ctx)) for ep in eps]
    entity_classes = sorted({c for _, pl in plans if pl for c in pl["classes"]})
    uses_guard = any(e.get("is_protected") for e in eps)

    nest_imports = ["Controller", "NotImplementedException", "Body", "Param", "Query"]
    nest_imports += [method_map.get(e["method"], "Get") for e in eps]
    if uses_guard:
        nest_imports += ["UseGuards", "Req"]

    out = ["// NestJS controller generated by Baxel",
           "// Auth + resource CRUD handlers are implemented; business actions (status changes, payments,",
           "// refunds, webhooks...) stay as 501 stubs for you to fill in.",
           f"import {{ {', '.join(sorted(set(nest_imports)))} }} from '@nestjs/common';",
           "import { CrudService } from './crud.service';",
           "import { AuthService } from './auth/auth.service';"]
    if uses_guard:
        out.append("import { JwtAuthGuard } from './auth/jwt-auth.guard';")
    if entity_classes:
        out.append(f"import {{ {', '.join(entity_classes)} }} from './entities/spec.entities';")
    out.append("\n@Controller()\nexport class AppController {")
    out.append("  constructor(private readonly crud: CrudService, private readonly auth: AuthService) {}\n")

    seen_names: set = set()
    implemented = 0
    for ep, plan in plans:
        name = _unique(camel_case(ep.get("summary") or ep["path"]), seen_names)
        deco = method_map.get(ep["method"], "Get")
        sig: List[str] = []
        if plan and plan["req"]:
            sig.append("@Req() req: any")
        sig += [f"@Param({json.dumps(p)}) {camel_case(p)}: string" for p in ep["params"]]
        if ep["method"] in ("POST", "PATCH", "PUT"):
            sig.append("@Body() body: Record<string, any>")
        if ep["method"] == "GET":
            sig.append("@Query() query: Record<string, any>")
        nest_path = re.sub(r"\{([^}]+)\}", r":\1", ep["path"])
        out.append(f"  // {ep.get('summary', '')}".rstrip())
        for label, key in (("Request", "request_payload_schema"), ("Response", "response_payload_schema")):
            if ep.get(key):
                out.append(f"  // {label}: {str(ep[key]).replace(chr(10), ' ')}")
        if ep.get("error_responses"):
            out.append(f"  // Errors: {', '.join(map(str, ep['error_responses']))}")
        out.append(f"  @{deco}({json.dumps(nest_path)})")
        if ep.get("is_protected"):
            out.append("  @UseGuards(JwtAuthGuard)")
        out.append(f"  async {name}({', '.join(sig)}) {{")
        if plan:
            implemented += 1
            out.extend("    " + ln for ln in plan["lines"])
        else:
            out.append(f"    throw new NotImplementedException({json.dumps(ep.get('summary') or ep['path'])});")
        out.append("  }\n")
    out.append("}\n")
    out.insert(3, f"// {implemented}/{len(plans)} endpoints implemented.")
    return "\n".join(out)


def generate_typescript_skeleton(spec: Any) -> Dict[str, str]:
    entities, _ = generate_ts_entities(spec)
    return {
        "models": entities,
        "routers": generate_ts_controller(spec),
        "services": "// Business logic & helpers\n",
    }


_CRUD_SERVICE_TS = r"""import { BadRequestException, ConflictException, ForbiddenException, Injectable, NotFoundException } from '@nestjs/common';
import { DataSource, EntityTarget } from 'typeorm';

// Never returned to clients, never writable through the generic endpoints.
const HIDDEN = ['password_hash'];
const READONLY = ['id', 'created_at', 'updated_at', 'password_hash'];

interface Owner { col: string; kind: string }
interface Opts { where?: Record<string, any>; owner?: Owner; user?: any }

/** Generic, safe-by-default persistence used by the generated controller. */
@Injectable()
export class CrudService {
  constructor(private readonly ds: DataSource) {}

  repo(entity: EntityTarget<any>) {
    return this.ds.getRepository(entity);
  }

  private cols(entity: EntityTarget<any>): string[] {
    return this.repo(entity).metadata.columns.map((c) => c.propertyName);
  }

  private strip(row: any) {
    if (!row) return row;
    const out = { ...row };
    for (const h of HIDDEN) delete out[h];
    return out;
  }

  /** Rows owned by an account are visible only to that account (when the token is of that account type). */
  private scope(o: Opts) {
    const where = { ...(o.where || {}) };
    if (o.owner && o.user && o.user.kind === o.owner.kind && where[o.owner.col] === undefined) {
      where[o.owner.col] = o.user.sub;
    }
    return where;
  }

  private writable(entity: EntityTarget<any>, body: any, owner?: Owner) {
    const cols = new Set(this.cols(entity));
    const src: Record<string, any> = { ...(body || {}) };
    if (src.name !== undefined && !cols.has('name') && cols.has('full_name')) src.full_name = src.name;
    const out: Record<string, any> = {};
    for (const k of Object.keys(src)) {
      if (cols.has(k) && !READONLY.includes(k) && k !== owner?.col) out[k] = src[k];
    }
    return out;
  }

  private async guard<T>(fn: () => Promise<T>): Promise<T> {
    try {
      return await fn();
    } catch (e: any) {
      const code = e?.driverError?.code || e?.code;
      if (code === '23505') throw new ConflictException('Already exists');
      if (['23502', '23503', '23514', '22P02', '22007', '22003'].includes(code)) {
        throw new BadRequestException(e?.driverError?.detail || e?.driverError?.message || 'Invalid request');
      }
      throw e;
    }
  }

  assertKind(user: any, kind: string) {
    if (!user || user.kind !== kind) throw new ForbiddenException();
  }

  assertSelf(user: any, kind: string, id: string) {
    this.assertKind(user, kind);
    if (user.sub !== id) throw new ForbiddenException();
  }

  list(entity: EntityTarget<any>, o: Opts & { query?: Record<string, any> }) {
    return this.guard(async () => {
      const cols = new Set(this.cols(entity));
      const where = this.scope(o);
      for (const [k, v] of Object.entries(o.query || {})) {
        if (cols.has(k) && !HIDDEN.includes(k) && where[k] === undefined) where[k] = v;
      }
      const take = Math.min(parseInt(String(o.query?.limit), 10) || 50, 100);
      const skip = parseInt(String(o.query?.offset), 10) || 0;
      const order: Record<string, 'DESC'> = cols.has('created_at') ? { created_at: 'DESC' } : {};
      const rows = await this.repo(entity).find({ where, take, skip, order });
      return rows.map((r) => this.strip(r));
    });
  }

  get(entity: EntityTarget<any>, o: Opts) {
    return this.guard(async () => {
      const row = await this.repo(entity).findOne({ where: this.scope(o) });
      if (!row) throw new NotFoundException();
      return this.strip(row);
    });
  }

  create(entity: EntityTarget<any>, body: any, o: Opts & { set?: Record<string, any> }) {
    return this.guard(async () => {
      const data: Record<string, any> = { ...this.writable(entity, body, o.owner), ...(o.set || {}) };
      if (o.owner && o.user && o.user.kind === o.owner.kind) data[o.owner.col] = o.user.sub;
      const repo = this.repo(entity);
      return this.strip(await repo.save(repo.create(data)));
    });
  }

  /** Trusted insert used by AuthService (may set password_hash). */
  createTrusted(entity: EntityTarget<any>, data: Record<string, any>) {
    return this.guard(async () => {
      const repo = this.repo(entity);
      return this.strip(await repo.save(repo.create(data)));
    });
  }

  update(entity: EntityTarget<any>, body: any, o: Opts) {
    return this.guard(async () => {
      const repo = this.repo(entity);
      const row = await repo.findOne({ where: this.scope(o) });
      if (!row) throw new NotFoundException();
      Object.assign(row, this.writable(entity, body, o.owner));
      if (this.cols(entity).includes('updated_at')) row.updated_at = new Date();
      return this.strip(await repo.save(row));
    });
  }

  remove(entity: EntityTarget<any>, o: Opts) {
    return this.guard(async () => {
      const repo = this.repo(entity);
      const row = await repo.findOne({ where: this.scope(o) });
      if (!row) throw new NotFoundException();
      await repo.remove(row);
      return { deleted: true };
    });
  }
}
"""

_AUTH_SERVICE_TS = r"""import { BadRequestException, ForbiddenException, Injectable, UnauthorizedException } from '@nestjs/common';
import { JwtService } from '@nestjs/jwt';
import * as bcrypt from 'bcryptjs';
import { CrudService } from '../crud.service';

/** Email/password auth: bcrypt hashes, short-lived access token + long-lived refresh token. */
@Injectable()
export class AuthService {
  constructor(private readonly jwt: JwtService, private readonly crud: CrudService) {}

  private async tokens(id: string, kind: string) {
    const access_token = await this.jwt.signAsync({ sub: id, kind, typ: 'access' });
    const refresh_token = await this.jwt.signAsync({ sub: id, kind, typ: 'refresh' }, { expiresIn: '7d' });
    return { access_token, refresh_token, token_type: 'bearer', expires_in: __EXPIRY__ };
  }

  async register(entity: any, kind: string, body: Record<string, any>) {
    if (!body?.email || !body?.password) throw new BadRequestException('email and password are required');
    if (String(body.password).length < 8) throw new BadRequestException('password must be at least 8 characters');
    const cols = new Set(this.crud.repo(entity).metadata.columns.map((c) => c.propertyName));
    const data: Record<string, any> = {};
    for (const [k, v] of Object.entries(body)) {
      if (cols.has(k) && !['id', 'password_hash', 'created_at', 'updated_at'].includes(k)) data[k] = v;
    }
    if (body.name !== undefined && !cols.has('name') && cols.has('full_name')) data.full_name = body.name;
    data.password_hash = await bcrypt.hash(String(body.password), 10);
    const user = await this.crud.createTrusted(entity, data);
    return { ...user, ...(await this.tokens(user.id, kind)) };
  }

  async login(entity: any, kind: string, body: Record<string, any>) {
    const field = body?.email ? 'email' : body?.username ? 'username' : null;
    if (!field || !body?.password) throw new BadRequestException('email and password are required');
    const user: any = await this.crud.repo(entity).findOne({ where: { [field]: body[field] } });
    const ok = user && (await bcrypt.compare(String(body.password), user.password_hash));
    if (!ok) throw new UnauthorizedException('Invalid credentials');
    if (user.is_active === false) throw new ForbiddenException('Account disabled');
    return { ...(await this.tokens(user.id, kind)), [kind + '_id']: user.id };
  }

  async refresh(body: Record<string, any>) {
    try {
      const p = await this.jwt.verifyAsync(String(body?.refresh_token));
      if (p.typ !== 'refresh') throw new Error('not a refresh token');
      return await this.tokens(p.sub, p.kind);
    } catch {
      throw new UnauthorizedException('Invalid refresh token');
    }
  }
}
"""


def build_typescript_project_files(spec: Any, jwt_secret: str = "") -> Dict[str, str]:
    """Static project files (boot, module, auth guard, package.json, Docker...) for the NestJS zip."""
    spec = as_dict(spec)
    expiry = ((spec.get("auth_strategy") or {}).get("token_expiry_seconds")) or 3600
    cache = ((spec.get("tech_stack") or {}).get("cache") or "").lower()
    env = f"DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres\nPORT=3000\nJWT_SECRET={jwt_secret or secrets.token_hex(32)}\n"
    if "redis" in cache:
        env += "REDIS_URL=redis://localhost:6379\n"

    return {
        "package.json": json.dumps({
            "name": "baxel-generated-api", "version": "1.0.0", "private": True,
            "scripts": {"build": "nest build", "start": "node dist/main", "start:dev": "nest start --watch"},
            "dependencies": {
                "@nestjs/common": "^10.3.0", "@nestjs/core": "^10.3.0",
                "@nestjs/platform-express": "^10.3.0", "@nestjs/typeorm": "^10.0.2",
                "@nestjs/jwt": "^10.2.0", "bcryptjs": "^2.4.3", "dotenv": "^16.4.5", "typeorm": "^0.3.20", "pg": "^8.11.5",
                "reflect-metadata": "^0.2.1", "rxjs": "^7.8.1",
            },
            "devDependencies": {"@nestjs/cli": "^10.3.2", "typescript": "^5.4.5", "@types/node": "^20.12.7", "@types/bcryptjs": "^2.4.6"},
        }, indent=2) + "\n",
        "tsconfig.json": json.dumps({"compilerOptions": {
            "module": "commonjs", "target": "ES2021", "experimentalDecorators": True,
            "emitDecoratorMetadata": True, "esModuleInterop": True, "skipLibCheck": True,
            "outDir": "./dist", "baseUrl": "./", "incremental": True,
        }, "include": ["src/**/*"]}, indent=2) + "\n",
        "nest-cli.json": json.dumps({"$schema": "https://json.schemastore.org/nest-cli",
                                      "collection": "@nestjs/schematics", "sourceRoot": "src"}, indent=2) + "\n",
        ".env": env,
        ".dockerignore": "node_modules\ndist\n.env\n",
        "Dockerfile": (
            "FROM node:20-alpine AS build\nWORKDIR /app\nCOPY package*.json ./\nRUN npm install\n"
            "COPY . .\nRUN npm run build\n\n"
            "FROM node:20-alpine\nWORKDIR /app\nENV NODE_ENV=production\nCOPY package*.json ./\n"
            "RUN npm install --omit=dev\nCOPY --from=build /app/dist ./dist\nCOPY migrations ./migrations\n"
            "EXPOSE 3000\nCMD [\"node\", \"dist/main\"]\n"
        ),
        "src/main.ts": (
            "import 'dotenv/config';\n"
            "import { NestFactory } from '@nestjs/core';\n"
            "import { DataSource } from 'typeorm';\n"
            "import { readFileSync } from 'fs';\nimport { join } from 'path';\n"
            "import { AppModule } from './app.module';\n\n"
            "async function bootstrap() {\n"
            "  if (!process.env.JWT_SECRET) throw new Error('JWT_SECRET is not set. Add it to .env or the environment.');\n"
            "  const app = await NestFactory.create(AppModule);\n"
            "  app.setGlobalPrefix('api');\n\n"
            "  // Apply the idempotent schema on every start so a fresh database just works.\n"
            "  const sql = readFileSync(join(process.cwd(), 'migrations', 'schema.sql'), 'utf8');\n"
            "  await app.get(DataSource).query(sql);\n\n"
            "  await app.listen(process.env.PORT || 3000);\n"
            "}\nbootstrap();\n"
        ),
        "src/app.module.ts": (
            "import { Module } from '@nestjs/common';\n"
            "import { TypeOrmModule } from '@nestjs/typeorm';\n"
            "import { JwtModule } from '@nestjs/jwt';\n"
            "import { AppController } from './app.controller';\n"
            "import { JwtAuthGuard } from './auth/jwt-auth.guard';\n"
            "import { AuthService } from './auth/auth.service';\n"
            "import { CrudService } from './crud.service';\n"
            "import { entities } from './entities/spec.entities';\n\n"
            "@Module({\n  imports: [\n"
            "    TypeOrmModule.forRoot({\n      type: 'postgres',\n      url: process.env.DATABASE_URL,\n"
            "      entities,\n      synchronize: false,\n    }),\n"
            "    TypeOrmModule.forFeature(entities),\n"
            "    JwtModule.register({\n      global: true,\n"
            "      secret: process.env.JWT_SECRET,\n"
            f"      signOptions: {{ expiresIn: {int(expiry)} }},\n    }}),\n"
            "  ],\n  controllers: [AppController],\n  providers: [JwtAuthGuard, AuthService, CrudService],\n})\n"
            "export class AppModule {}\n"
        ),
        "src/crud.service.ts": _CRUD_SERVICE_TS,
        "src/auth/auth.service.ts": _AUTH_SERVICE_TS.replace("__EXPIRY__", str(int(expiry))),
        "src/auth/jwt-auth.guard.ts": (
            "import { CanActivate, ExecutionContext, Injectable, UnauthorizedException } from '@nestjs/common';\n"
            "import { JwtService } from '@nestjs/jwt';\n\n"
            "@Injectable()\nexport class JwtAuthGuard implements CanActivate {\n"
            "  constructor(private readonly jwt: JwtService) {}\n\n"
            "  async canActivate(context: ExecutionContext): Promise<boolean> {\n"
            "    const req = context.switchToHttp().getRequest();\n"
            "    const [type, token] = (req.headers['authorization'] || '').split(' ');\n"
            "    if (type !== 'Bearer' || !token) throw new UnauthorizedException();\n"
            "    try {\n      req.user = await this.jwt.verifyAsync(token);\n"
            "      if (req.user.typ === 'refresh') throw new Error('refresh token cannot access resources');\n"
            "    } catch {\n      throw new UnauthorizedException();\n    }\n"
            "    return true;\n  }\n}\n"
        ),
    }


# ---------------------------------------------------------------------------
# Python / FastAPI
# ---------------------------------------------------------------------------

_PY_RESERVED_ATTRS = {"metadata", "registry"}
# Names the generated router module already uses; a handler must not shadow them.
_PY_ROUTER_NAMES = {"router", "get_db", "get_current_user", "Session", "Request", "Body", "Depends",
                    "APIRouter", "HTTPException", "_auth", "_crud"}


def _py_name(name: str) -> str:
    out = snake_case(name)
    return out + "_" if keyword.iskeyword(out) else out


def _render_py(plan: Optional[Dict[str, Any]], ctx: _Ctx) -> Optional[Dict[str, Any]]:
    if not plan:
        return None
    op = plan["op"]
    if op == "refresh":
        return {"lines": ["return _auth.refresh(body)"], "classes": set(), "db": False, "request": False}
    cls = ctx.cls[plan["table"]]
    if op in ("login", "register"):
        return {"lines": [f"return _auth.{op}(db, {cls}, {json.dumps(plan['table'])}, body)"],
                "classes": {cls}, "db": True, "request": False}

    def expr(e):
        return 'current_user["sub"]' if e[0] == "user" else _py_name(e[1])

    lines: List[str] = []
    for a in plan["asserts"]:
        if a[0] == "kind":
            lines.append(f"_crud.assert_kind(current_user, {json.dumps(a[1])})")
        else:
            lines.append(f"_crud.assert_self(current_user, {json.dumps(a[1])}, {_py_name(a[2])})")
    w = "{" + ", ".join(f"{json.dumps(c)}: {expr(e)}" for c, e in plan["where"]) + "}"
    user = "current_user" if plan["protected"] else "None"
    o = f"({json.dumps(plan['owner'][0])}, {json.dumps(plan['owner'][1])})" if plan["owner"] else "None"
    call = {
        "list": f"return _crud.list_rows(db, {cls}, where={w}, owner={o}, user={user}, query=dict(request.query_params))",
        "get": f"return _crud.get_row(db, {cls}, where={w}, owner={o}, user={user})",
        "create": f"return _crud.create_row(db, {cls}, body, set_values={w}, owner={o}, user={user})",
        "update": f"return _crud.update_row(db, {cls}, body, where={w}, owner={o}, user={user})",
        "remove": f"return _crud.remove_row(db, {cls}, where={w}, owner={o}, user={user})",
    }[op]
    return {"lines": lines + [call], "classes": {cls}, "db": True, "request": op == "list"}


def generate_python_skeleton(spec: Any) -> Dict[str, str]:
    spec = as_dict(spec)
    ctx = _Ctx(spec)
    sa_types = {"uuid": "Uuid(as_uuid=False)", "int": "Integer", "bigint": "BigInteger", "numeric": "Numeric(12, 2)",
                "float": "Float", "bool": "Boolean", "timestamp": "DateTime", "date": "Date", "json": "JSONB",
                "text": "Text", "enum": "String(50)", "string": "String(255)"}
    models = [
        "# SQLAlchemy models generated by Baxel\n\n",
        "import uuid\n\n",
        "from sqlalchemy import BigInteger, Boolean, Column, Date, DateTime, Float, ForeignKey, Integer, Numeric, String, Text, Uuid, func\n",
        "from sqlalchemy.dialects.postgresql import JSONB\n",
        "from sqlalchemy.orm import declarative_base\n\nBase = declarative_base()\n\n\n",
    ]
    for t in spec["database"]["tables"]:
        models.append(f"class {ctx.cls[t['name']]}(Base):\n")
        models.append(f"    __tablename__ = {t['name']!r}\n")
        if t.get("description"):
            models.append(f"    # {t['description']}\n")
        models.append("\n")
        for c in t["columns"]:
            kind = column_kind(c)
            attr = _py_name(c["name"])
            if attr in _PY_RESERVED_ATTRS:
                attr += "_"
            args = [] if attr == c["name"] else [repr(c["name"])]
            args.append(sa_types[kind])
            fk = _fk_parts(c, ctx.names)
            if fk:  # positional args must come before keyword args
                args.append(f"ForeignKey({fk[0] + '.' + fk[1]!r})")
            if c.get("is_primary_key"):
                args.append("primary_key=True")
                if kind == "uuid":
                    args.append("default=lambda: str(uuid.uuid4())")
            elif not c.get("is_nullable"):
                args.append("nullable=False")
            if kind == "timestamp" and _sql_default(c, kind):
                args.append("server_default=func.now()")
            models.append(f"    {attr} = Column({', '.join(args)})\n")
        models.append("\n\n")

    eps = _normalise_endpoints(spec.get("endpoints", []), strip_api_prefix=True)
    plans = [(ep, _render_py(_plan(ep, ctx), ctx)) for ep in eps]
    classes = sorted({c for _, pl in plans if pl for c in pl["classes"]})
    implemented = sum(1 for _, pl in plans if pl)
    routers = [
        "# FastAPI routers generated by Baxel\n",
        f"# {implemented}/{len(plans)} endpoints implemented: auth and resource CRUD. Business actions\n",
        "# (status changes, payments, refunds, webhooks...) return 501 for you to fill in.\n\n",
        "from fastapi import APIRouter, Body, Depends, HTTPException, Request\n",
        "from sqlalchemy.orm import Session\n\n",
        "from app.core import auth as _auth, crud as _crud\n",
        "from app.core.auth import get_current_user\n",
        "from app.core.db import get_db\n",
    ]
    if classes:
        routers.append(f"from app.models.spec_models import {', '.join(classes)}\n")
    routers.append("\nrouter = APIRouter()\n\n\n")

    seen_names = set(_PY_ROUTER_NAMES) | set(ctx.cls.values())
    for ep, plan in plans:
        name = _unique(_py_name(ep.get("summary") or ep["path"]), seen_names)
        path = re.sub(r"\{([^}]+)\}", lambda m: "{" + _py_name(m.group(1)) + "}", ep["path"])
        for label, key in (("Request", "request_payload_schema"), ("Response", "response_payload_schema")):
            if ep.get(key):
                routers.append(f"# {label}: {str(ep[key]).replace(chr(10), ' ')}\n")
        if ep.get("error_responses"):
            routers.append(f"# Errors: {', '.join(map(str, ep['error_responses']))}\n")
        routers.append(f"@router.{ep['method'].lower()}({path!r}, summary={ep.get('summary', '')!r})\n")
        sig = [f"{_py_name(p)}: str" for p in ep["params"]]
        if plan and plan["request"]:
            sig.append("request: Request")
        if plan and ep["method"] in ("POST", "PATCH", "PUT"):
            sig.append("body: dict = Body(default={})")
        if plan and plan["db"]:
            sig.append("db: Session = Depends(get_db)")
        if ep.get("is_protected"):
            sig.append("current_user: dict = Depends(get_current_user)")
        routers.append(f"def {name}({', '.join(sig)}):\n")
        if plan:
            routers.extend(f"    {ln}\n" for ln in plan["lines"])
        else:
            routers.append(f"    raise HTTPException(status_code=501, detail={(ep.get('summary') or ep['path'])!r})\n")
        routers.append("\n\n")
    return {"models": "".join(models), "routers": "".join(routers), "services": "# Business logic & helpers\n"}


_PY_DB = r"""import os
import re

from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

load_dotenv()

# Accept postgres:// and async driver URLs; this app uses psycopg2.
DATABASE_URL = re.sub(r"^postgres(ql)?(\+\w+)?://", "postgresql+psycopg2://", os.environ["DATABASE_URL"])

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
"""

_PY_MAIN = r"""from contextlib import asynccontextmanager
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
if not os.getenv("JWT_SECRET"):
    raise RuntimeError("JWT_SECRET is not set. Add it to .env or the environment.")

from fastapi import FastAPI

from app.core.db import engine
from app.routes.endpoints import router as api_router


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Apply the idempotent schema on every start so a fresh database just works.
    sql = (Path(__file__).resolve().parent.parent / "migrations" / "schema.sql").read_text(encoding="utf-8")
    conn = engine.raw_connection()
    try:
        conn.cursor().execute(sql)
        conn.commit()
    finally:
        conn.close()
    yield


app = FastAPI(title="Baxel Generated API", lifespan=lifespan)
app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    return {"message": "API is running."}
"""

_PY_CRUD = r"""# Generic, safe-by-default persistence used by the generated routes.
import datetime as dt
from contextlib import contextmanager

from fastapi import HTTPException
from sqlalchemy import insert, inspect, select
from sqlalchemy.exc import DataError, DBAPIError, IntegrityError, StatementError

# Never returned to clients, never writable through the generic endpoints.
HIDDEN = {"password_hash"}
READONLY = {"id", "created_at", "updated_at", "password_hash"}


def attrs(model):
    # column name -> model attribute name
    return {a.columns[0].name: a.key for a in inspect(model).column_attrs}


def to_dict(row):
    return {name: getattr(row, key) for name, key in attrs(type(row)).items() if name not in HIDDEN}


@contextmanager
def guard(db):
    try:
        yield
    except IntegrityError as e:
        db.rollback()
        if getattr(e.orig, "pgcode", None) == "23505":
            raise HTTPException(status_code=409, detail="Already exists")
        raise HTTPException(status_code=400, detail=str(e.orig).strip())
    except DataError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e.orig).strip())
    except StatementError as e:
        db.rollback()
        if isinstance(e, DBAPIError):
            raise
        raise HTTPException(status_code=400, detail="Invalid request")


def assert_kind(user, kind):
    if not user or user.get("kind") != kind:
        raise HTTPException(status_code=403, detail="Forbidden")


def assert_self(user, kind, row_id):
    assert_kind(user, kind)
    if user.get("sub") != row_id:
        raise HTTPException(status_code=403, detail="Forbidden")


def _scope(where, owner, user):
    # Rows owned by an account are visible only to that account (when the token is of that account type).
    out = dict(where or {})
    if owner and user and user.get("kind") == owner[1] and owner[0] not in out:
        out[owner[0]] = user["sub"]
    return out


def _select(model, where):
    names = attrs(model)
    return select(model).filter_by(**{names[k]: v for k, v in where.items()})


def _writable(model, body, owner=None):
    names = attrs(model)
    src = dict(body or {})
    if "name" in src and "name" not in names and "full_name" in names:
        src["full_name"] = src["name"]
    return {names[k]: v for k, v in src.items()
            if k in names and k not in READONLY and (not owner or k != owner[0])}


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def find_one(db, model, where):
    with guard(db):
        return db.scalars(_select(model, where)).first()


def _required(db, model, where):
    row = find_one(db, model, where)
    if row is None:
        raise HTTPException(status_code=404, detail="Not found")
    return row


def list_rows(db, model, where=None, owner=None, user=None, query=None):
    names = attrs(model)
    query = query or {}
    scoped = _scope(where, owner, user)
    for key, value in query.items():
        if key in names and key not in HIDDEN and key not in scoped:
            scoped[key] = value
    stmt = _select(model, scoped)
    if "created_at" in names:
        stmt = stmt.order_by(getattr(model, names["created_at"]).desc())
    stmt = stmt.limit(min(_int(query.get("limit"), 50) or 50, 100)).offset(max(_int(query.get("offset"), 0), 0))
    with guard(db):
        return [to_dict(r) for r in db.scalars(stmt).all()]


def get_row(db, model, where=None, owner=None, user=None):
    return to_dict(_required(db, model, _scope(where, owner, user)))


def create_trusted(db, model, values):
    # Column-name keyed insert; callers decide what may be set (AuthService sets password_hash).
    # A plain insert leaves out unsupplied columns so database defaults apply (the ORM would send NULL).
    names = attrs(model)
    data = {getattr(model, names[k]): v for k, v in values.items() if k in names}
    with guard(db):
        out = to_dict(db.scalars(insert(model).values(data).returning(model)).one())
        db.commit()
        return out


def create_row(db, model, body, set_values=None, owner=None, user=None):
    columns = {key: name for name, key in attrs(model).items()}
    values = {columns[k]: v for k, v in _writable(model, body, owner).items()}
    values.update(set_values or {})
    if owner and user and user.get("kind") == owner[1]:
        values[owner[0]] = user["sub"]
    return create_trusted(db, model, values)


def update_row(db, model, body, where=None, owner=None, user=None):
    row = _required(db, model, _scope(where, owner, user))
    names = attrs(model)
    with guard(db):
        for key, value in _writable(model, body, owner).items():
            setattr(row, key, value)
        if "updated_at" in names:
            setattr(row, names["updated_at"], dt.datetime.now(dt.timezone.utc).replace(tzinfo=None))
        db.commit()
        db.refresh(row)
        return to_dict(row)


def remove_row(db, model, where=None, owner=None, user=None):
    row = _required(db, model, _scope(where, owner, user))
    with guard(db):
        db.delete(row)
        db.commit()
    return {"deleted": True}
"""

_PY_AUTH = r"""# Email/password auth: bcrypt hashes, short-lived access token + long-lived refresh token.
import datetime as dt
import os

import bcrypt
import jwt
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from app.core import crud

ACCESS_SECONDS = __EXPIRY__
REFRESH_SECONDS = 7 * 24 * 3600

_bearer = HTTPBearer(auto_error=False)


def _secret():
    return os.environ["JWT_SECRET"]


def _sign(sub, kind, typ, seconds):
    now = dt.datetime.now(dt.timezone.utc)
    payload = {"sub": str(sub), "kind": kind, "typ": typ, "iat": now, "exp": now + dt.timedelta(seconds=seconds)}
    return jwt.encode(payload, _secret(), algorithm="HS256")


def _tokens(sub, kind):
    return {
        "access_token": _sign(sub, kind, "access", ACCESS_SECONDS),
        "refresh_token": _sign(sub, kind, "refresh", REFRESH_SECONDS),
        "token_type": "bearer",
        "expires_in": ACCESS_SECONDS,
    }


def _password_bytes(password):
    return str(password).encode("utf-8")[:72]  # bcrypt's input limit


def get_current_user(creds: HTTPAuthorizationCredentials = Depends(_bearer)):
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="Unauthorized")
    try:
        payload = jwt.decode(creds.credentials, _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if payload.get("typ") == "refresh":
        raise HTTPException(status_code=401, detail="Unauthorized")
    return payload


def register(db, model, kind, body):
    if not body.get("email") or not body.get("password"):
        raise HTTPException(status_code=400, detail="email and password are required")
    if len(str(body["password"])) < 8:
        raise HTTPException(status_code=400, detail="password must be at least 8 characters")
    names = crud.attrs(model)
    data = {k: v for k, v in body.items() if k in names and k not in crud.READONLY}
    if "name" in body and "name" not in names and "full_name" in names:
        data["full_name"] = body["name"]
    data["password_hash"] = bcrypt.hashpw(_password_bytes(body["password"]), bcrypt.gensalt()).decode("utf-8")
    user = crud.create_trusted(db, model, data)
    return {**user, **_tokens(user["id"], kind)}


def login(db, model, kind, body):
    field = "email" if body.get("email") else "username" if body.get("username") else None
    if not field or not body.get("password"):
        raise HTTPException(status_code=400, detail="email and password are required")
    if field not in crud.attrs(model):
        raise HTTPException(status_code=400, detail="email and password are required")
    user = crud.find_one(db, model, {field: body[field]})
    if user is None or not bcrypt.checkpw(_password_bytes(body["password"]), user.password_hash.encode("utf-8")):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    if getattr(user, "is_active", True) is False:
        raise HTTPException(status_code=403, detail="Account disabled")
    return {**_tokens(user.id, kind), f"{kind}_id": str(user.id)}


def refresh(body):
    try:
        payload = jwt.decode(str(body.get("refresh_token")), _secret(), algorithms=["HS256"])
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    if payload.get("typ") != "refresh":
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return _tokens(payload["sub"], payload["kind"])
"""


def build_python_project_files(spec: Any, jwt_secret: str = "") -> Dict[str, str]:
    """Static project files for the FastAPI zip."""
    spec = as_dict(spec)
    expiry = ((spec.get("auth_strategy") or {}).get("token_expiry_seconds")) or 3600
    return {
        "requirements.txt": (
            "fastapi>=0.110\nuvicorn[standard]>=0.27\npydantic>=2.0\nsqlalchemy>=2.0.20\npsycopg2-binary>=2.9.6\n"
            "python-dotenv>=1.0.0\nPyJWT>=2.8\nbcrypt>=4.1\n"
        ),
        ".env": ("DATABASE_URL=postgresql://postgres:postgres@localhost:5432/postgres\n"
                 f"PORT=8000\nJWT_SECRET={jwt_secret or secrets.token_hex(32)}\n"),
        ".dockerignore": "venv\n.venv\n__pycache__\n.env\n",
        "Dockerfile": (
            "FROM python:3.12-slim\nWORKDIR /code\nCOPY requirements.txt .\n"
            "RUN pip install --no-cache-dir -r requirements.txt\nCOPY app ./app\nCOPY migrations ./migrations\n"
            "EXPOSE 8000\nCMD [\"sh\", \"-c\", \"uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}\"]\n"
        ),
        "app/__init__.py": "",
        "app/core/__init__.py": "",
        "app/models/__init__.py": "",
        "app/routes/__init__.py": "",
        "app/main.py": _PY_MAIN,
        "app/core/db.py": _PY_DB,
        "app/core/crud.py": _PY_CRUD,
        "app/core/auth.py": _PY_AUTH.replace("__EXPIRY__", str(int(expiry))),
    }


def generate_code_skeleton(spec: Any) -> Dict[str, str]:
    spec = as_dict(spec)
    return (generate_typescript_skeleton if detect_stack_family(spec["tech_stack"]["language"]) == "typescript"
            else generate_python_skeleton)(spec)


def detect_stack_family(language: str) -> str:
    lang = (language or "").strip().lower()
    ts_keywords = ("typescript", "javascript", "node", "nestjs", "nest.js", "next.js", "express")
    return "typescript" if lang in ("js", "ts") or any(k in lang for k in ts_keywords) else "python"


# ---------------------------------------------------------------------------
# Zip contents (works for runs stored by any generator version)
# ---------------------------------------------------------------------------

_PUBLIC_ROUTE = re.compile(r"(log.?in|sign.?in|sign.?up|register|authenticate|refresh|webhook)", re.I)


def _route_key(method: str, path: str) -> Tuple[str, str]:
    path = _PARAM_RE.sub("{}", "/" + (path or "/").strip("/"))
    if path == "/api" or path.startswith("/api/"):
        path = path[4:] or "/"
    return method.upper(), path


def _stored_protection(routers: str) -> Dict[Tuple[str, str], bool]:
    """Which routes were guarded, read back from the code stored with an older run."""
    lines = routers.splitlines()
    found: Dict[Tuple[str, str], bool] = {}
    for i, line in enumerate(lines):
        m = re.match(r"""\s*@(?:router\.)?(get|post|put|patch|delete)\(\s*['"]([^'"]+)['"]""", line, re.I)
        if m:
            found[_route_key(m.group(1), m.group(2))] = bool(
                re.search(r"auth guard|UseGuards|get_current_user", " ".join(lines[i + 1:i + 4])))
    return found


def _spec_from_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Rebuilds a generator spec from the flattened shape stored in pipeline_runs.result.

    The stored shape has no enum values, so enums lose their CHECK constraint when the stored SQL
    has to be regenerated too. Route protection comes from the stored code where it can be read.
    """
    protection = _stored_protection((result.get("code_skeleton") or {}).get("routers") or "")
    fks: Dict[Tuple[str, str], str] = {}
    for rel in result.get("relationships") or []:
        left, _, right = rel.partition("->")
        table, _, column = left.strip().partition(".")
        fks[(table, column)] = right.strip()
    tables = []
    for entity in result.get("entities") or []:
        columns = []
        for field in entity.get("fields") or []:
            constraints = field.get("constraints") or []
            is_pk = "primary_key" in constraints
            columns.append({
                "name": field["name"], "type": field.get("type") or "String", "is_primary_key": is_pk,
                "is_nullable": not is_pk and "not_null" not in constraints,
                "foreign_key": fks.get((entity["name"], field["name"])), "enum_values": None,
            })
        tables.append({"name": entity["name"], "description": "", "columns": columns})
    endpoints = [{
        "method": ep.get("method") or "GET", "path": ep.get("path") or "/", "summary": ep.get("desc") or "",
        "is_protected": protection.get(_route_key(ep.get("method") or "GET", ep.get("path") or "/"), not (
            (ep.get("method") or "").upper() == "POST"
            and _PUBLIC_ROUTE.search(f"{ep.get('path')} {ep.get('desc')}"))),
        "error_responses": ep.get("errors") or None,
    } for ep in result.get("endpoints") or []]
    return {"database": {"tables": tables}, "endpoints": endpoints,
            "tech_stack": result.get("tech_stack") or {"language": ""},
            "auth_strategy": result.get("auth_strategy") or {}}


def upgrade_result(result: Dict[str, Any]) -> Dict[str, Any]:
    """Returns the stored result with code from the current generator (older runs are regenerated)."""
    meta = result.get("__meta") or {}
    if meta.get("scaffold_version") == SCAFFOLD_VERSION:
        return result
    spec = _spec_from_result(result)
    stored_sql = result.get("migration_sql") or ""
    return {
        **result,
        "code_skeleton": generate_code_skeleton(spec),
        # Keep SQL from the fixed generator: it still has the enum CHECKs the stored shape dropped.
        "migration_sql": stored_sql if "Idempotent" in stored_sql else generate_migration_sql(spec),
        "__meta": {**meta, "scaffold_version": SCAFFOLD_VERSION},
    }


def _compose_with_secret(compose: str, jwt_secret: str) -> str:
    """The LLM often writes a placeholder JWT secret; use the one generated for this download."""
    def swap(match: "re.Match[str]") -> str:
        return match.group(0) if "${" in match.group(2) else match.group(1) + jwt_secret
    return re.sub(r"(JWT_SECRET\s*[:=]\s*)([^\n#]*)", swap, compose)


def _default_compose(port: int, jwt_secret: str) -> str:
    return (
        "services:\n  web:\n    build: .\n    ports:\n"
        f"      - \"{port}:{port}\"\n    environment:\n"
        "      DATABASE_URL: postgresql://postgres:postgres@db:5432/postgres\n"
        f"      JWT_SECRET: {jwt_secret}\n      PORT: \"{port}\"\n"
        "    depends_on:\n      db:\n        condition: service_healthy\n"
        "  db:\n    image: postgres:16-alpine\n    environment:\n"
        "      POSTGRES_PASSWORD: postgres\n    healthcheck:\n"
        "      test: [\"CMD-SHELL\", \"pg_isready -U postgres\"]\n      interval: 5s\n      retries: 10\n"
    )


def build_scaffold_files(result: Dict[str, Any]) -> Dict[str, str]:
    """Every file in the downloadable zip, keyed by path."""
    result = upgrade_result(result)
    jwt_secret = secrets.token_hex(32)
    code = result.get("code_skeleton") or {}
    is_ts = detect_stack_family((result.get("tech_stack") or {}).get("language", "")) == "typescript"
    compose = (result.get("devops") or {}).get("docker_compose_content")
    files = {
        "migrations/schema.sql": result.get("migration_sql") or "-- No migration sql generated\n",
        "docker-compose.yml": (_compose_with_secret(compose, jwt_secret) if compose
                               else _default_compose(3000 if is_ts else 8000, jwt_secret)),
    }
    if is_ts:
        files.update(build_typescript_project_files(result, jwt_secret))
        files["src/entities/spec.entities.ts"] = code.get("models") or "// No entities generated\n"
        files["src/app.controller.ts"] = code.get("routers") or "// No routes generated\n"
        files["src/app.service.ts"] = code.get("services") or "// No services generated\n"
    else:
        files.update(build_python_project_files(result, jwt_secret))
        files["app/models/spec_models.py"] = code.get("models") or "# No models generated\n"
        files["app/routes/endpoints.py"] = code.get("routers") or "# No routes generated\n"
    return files
