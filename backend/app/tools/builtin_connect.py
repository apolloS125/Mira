"""Connector wizard — introspect an OpenAPI spec and draft skills per operation.

The wizard produces drafts (not active skills). The user reviews and approves
via Telegram /drafts. Mutating operations (POST/PUT/PATCH/DELETE) are flagged
`confirmation_required=true` so the UX can warn the user before activation.

Auth handling: the wizard inspects `components.securitySchemes` and binds the
generated skill to a named secret (e.g. `secrets.get("WEATHER_API_KEY")`)
instead of taking auth tokens as runtime args. The user creates the secret via
Telegram /secret_add NAME.
"""
from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.skills import registry as skill_registry
from app.tools.builtin_http import _validate_url
from app.tools.registry import register

ALLOWED_METHODS = {"get", "post", "put", "patch", "delete"}
SAFE_METHODS = {"get"}
_NAME_RE = re.compile(r"[^a-z0-9_]+")
_DISCOVERY_PATHS = (
    "/openapi.json",
    "/openapi.yaml",
    "/swagger.json",
    "/.well-known/openapi",
    "/v1/openapi.json",
    "/api/openapi.json",
)


def _slugify(s: str) -> str:
    s = s.strip().lower().replace("-", "_").replace(" ", "_")
    s = _NAME_RE.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60] or "op"


def _params_schema(op: dict, body_schema: dict | None) -> dict:
    """Convert OpenAPI parameters + requestBody → JSON schema for skill args."""
    props: dict[str, Any] = {}
    required: list[str] = []
    for p in op.get("parameters", []) or []:
        name = p.get("name")
        if not name:
            continue
        schema = p.get("schema") or {"type": "string"}
        props[name] = {
            **schema,
            "description": p.get("description", f"{p.get('in', 'query')} param"),
        }
        if p.get("required"):
            required.append(name)
    if body_schema:
        props["body"] = {
            **body_schema,
            "description": "Request body (JSON)",
        }
        # Mark body required if requestBody.required is true.
        if op.get("requestBody", {}).get("required"):
            required.append("body")
    out: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        out["required"] = required
    return out


def _detect_auth(spec: dict) -> tuple[str | None, str | None]:
    """Inspect securitySchemes; return (header_name, secret_name_hint)."""
    schemes = (spec.get("components") or {}).get("securitySchemes") or {}
    for name, sch in schemes.items():
        if not isinstance(sch, dict):
            continue
        t = (sch.get("type") or "").lower()
        if t == "apikey" and (sch.get("in") or "").lower() == "header":
            header = sch.get("name") or "Authorization"
            return header, _slugify(name).upper() + "_KEY"
        if t == "http" and (sch.get("scheme") or "").lower() == "bearer":
            return "Authorization", _slugify(name).upper() + "_TOKEN"
    return None, None


def _render_skill_code(
    *,
    method: str,
    path: str,
    base_url: str,
    parameters: list[dict],
    has_body: bool,
    auth_header: str | None,
    secret_name: str | None,
    auth_scheme: str = "raw",  # "raw" | "bearer"
) -> str:
    path_params = [p["name"] for p in parameters if p.get("in") == "path"]
    query_params = [p["name"] for p in parameters if p.get("in") == "query"]
    header_params = [p["name"] for p in parameters if p.get("in") == "header"]

    auth_block = ""
    if auth_header and secret_name:
        prefix = "Bearer " if auth_scheme == "bearer" else ""
        auth_block = (
            f"    _token = await secrets.get({secret_name!r})\n"
            f"    if _token:\n"
            f"        headers[{auth_header!r}] = {prefix!r} + _token\n"
        )

    body_block = (
        "    body = args.get('body')\n"
        if has_body
        else "    body = None\n"
    )

    return f"""\
import httpx

BASE_URL = {base_url!r}
METHOD = {method.upper()!r}
PATH = {path!r}
PATH_PARAMS = {path_params!r}
QUERY_PARAMS = {query_params!r}
HEADER_PARAMS = {header_params!r}

async def run(args):
    path = PATH
    for p in PATH_PARAMS:
        if p in args:
            path = path.replace("{{" + p + "}}", str(args[p]))
    url = BASE_URL.rstrip("/") + path
    params = {{k: args[k] for k in QUERY_PARAMS if k in args}}
    headers = {{k: args[k] for k in HEADER_PARAMS if k in args}}
{auth_block}{body_block}    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.request(METHOD, url, params=params or None, headers=headers or None, json=body)
    text = resp.text
    if len(text) > 4000:
        text = text[:4000] + "...[truncated]"
    try:
        data = resp.json()
    except Exception:
        data = None
    return {{"status": resp.status_code, "json": data, "text": text if data is None else None}}
"""


async def _fetch_spec(client: httpx.AsyncClient, candidate: str) -> tuple[str, dict] | None:
    if _validate_url(candidate):
        return None
    try:
        resp = await client.get(candidate)
        if resp.status_code == 200:
            return candidate, resp.json()
    except Exception:
        return None
    return None


@register(
    name="connect_http_api",
    description=(
        "Introspect an OpenAPI/Swagger spec and draft one skill per operation. "
        "Drafts go to /drafts for user approval. Mutating ops (POST/PUT/PATCH/DELETE) "
        "are flagged with confirmation_required so the UX can warn the user. "
        "If `openapi_url` is a bare host, the wizard probes common discovery paths "
        "(/openapi.json, /swagger.json, etc.). Auth is auto-detected from "
        "components.securitySchemes and bound to a named secret — the user must "
        "set the secret value via Telegram /secret_add NAME."
    ),
    parameters={
        "type": "object",
        "properties": {
            "openapi_url": {
                "type": "string",
                "description": "URL to the OpenAPI JSON spec, OR a bare host to auto-discover",
            },
            "base_url": {"type": "string", "description": "Base URL if spec lacks `servers`"},
            "secret_name": {
                "type": "string",
                "description": "Name of the secret holding the auth token (overrides auto-detected name)",
            },
            "prefix": {
                "type": "string",
                "default": "api",
                "description": "Prefix for skill names, e.g. 'weather' → weather_get_forecast",
            },
            "max_ops": {"type": "integer", "default": 10, "minimum": 1, "maximum": 50},
            "include_mutations": {
                "type": "boolean",
                "default": True,
                "description": "Set false to draft only safe (GET) operations.",
            },
        },
        "required": ["openapi_url"],
    },
)
async def _connect(args: dict):
    url = args["openapi_url"]
    err = _validate_url(url)
    if err:
        return {"ok": False, "error": f"openapi_url rejected: {err}"}
    prefix = _slugify(args.get("prefix") or "api")
    max_ops = int(args.get("max_ops") or 10)
    include_mutations = bool(args.get("include_mutations", True))
    secret_override = args.get("secret_name")

    spec: dict | None = None
    spec_url = url
    # follow_redirects disabled so attacker cannot redirect to internal IPs.
    async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
        # Try the URL directly first.
        try:
            resp = await client.get(url)
            if resp.status_code == 200:
                try:
                    spec = resp.json()
                except Exception:
                    spec = None
        except Exception:
            spec = None

        # Fallback: discovery from a bare host.
        if spec is None:
            parts = urlsplit(url)
            if parts.scheme and parts.netloc:
                base = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
                for p in _DISCOVERY_PATHS:
                    hit = await _fetch_spec(client, base + p)
                    if hit:
                        spec_url, spec = hit
                        break

    if spec is None:
        return {"ok": False, "error": f"could not load OpenAPI spec at {url}"}

    servers = spec.get("servers") or []
    base_url = args.get("base_url") or (servers[0].get("url") if servers else None)
    if not base_url:
        # Fall back to the spec host.
        parts = urlsplit(spec_url)
        if parts.scheme and parts.netloc:
            base_url = urlunsplit((parts.scheme, parts.netloc, "", "", ""))
    if not base_url:
        return {"ok": False, "error": "no base_url (spec has no servers, none provided)"}
    # Validate base_url to prevent the spec from coercing drafted skills toward
    # internal IPs (cloud metadata, LiteLLM proxy, Redis, Qdrant, etc.).
    base_err = _validate_url(base_url)
    if base_err:
        return {"ok": False, "error": f"base_url rejected: {base_err}"}

    auth_header, auto_secret = _detect_auth(spec)
    secret_name = secret_override or auto_secret
    auth_scheme = "raw"
    schemes = (spec.get("components") or {}).get("securitySchemes") or {}
    for sch in schemes.values():
        if isinstance(sch, dict) and (sch.get("type") or "").lower() == "http" and (sch.get("scheme") or "").lower() == "bearer":
            auth_scheme = "bearer"
            break

    drafted: list[dict] = []
    for path, ops in (spec.get("paths") or {}).items():
        if not isinstance(ops, dict):
            continue
        for method, op in ops.items():
            m = method.lower()
            if m not in ALLOWED_METHODS:
                continue
            if m not in SAFE_METHODS and not include_mutations:
                continue
            if not isinstance(op, dict):
                continue
            op_id = op.get("operationId") or f"{m}_{path}"
            skill_name = f"{prefix}_{_slugify(op_id)}"[:64]

            body_schema = None
            req_body = op.get("requestBody") or {}
            content = req_body.get("content") or {}
            json_ct = content.get("application/json") or {}
            if json_ct:
                body_schema = json_ct.get("schema")

            schema = _params_schema(op, body_schema)
            code = _render_skill_code(
                method=m,
                path=path,
                base_url=base_url,
                parameters=op.get("parameters") or [],
                has_body=body_schema is not None,
                auth_header=auth_header,
                secret_name=secret_name,
                auth_scheme=auth_scheme,
            )
            confirmation_required = m not in SAFE_METHODS
            try:
                await skill_registry.save_draft(
                    name=skill_name,
                    description=(op.get("summary") or op.get("description") or f"{m.upper()} {path}")[:300],
                    parameters=schema,
                    code=code,
                    author="agent",
                    confirmation_required=confirmation_required,
                )
            except Exception as e:
                drafted.append({"name": skill_name, "error": str(e)})
                continue
            drafted.append({
                "name": skill_name,
                "method": m.upper(),
                "summary": op.get("summary") or path,
                "confirmation_required": confirmation_required,
            })
            if len(drafted) >= max_ops:
                break
        if len(drafted) >= max_ops:
            break

    msg = (
        f"Drafted {len(drafted)} skill(s) from {spec_url}. "
        "Tell the user to run /drafts in Telegram to approve."
    )
    if secret_name:
        msg += f" Auth requires secret `{secret_name}` — user must set it via /secret_add {secret_name}."
    return {
        "ok": True,
        "spec_url": spec_url,
        "base_url": base_url,
        "auth_header": auth_header,
        "secret_name": secret_name,
        "drafts": drafted,
        "message": msg,
    }
