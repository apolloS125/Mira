"""Connector wizard — introspect an OpenAPI spec and draft skills per operation.

The wizard produces drafts (not saved skills). The agent is expected to
present the generated list to the user, then call `confirm_skill` for the
ones the user wants to keep. This keeps the human in the loop for anything
that touches external services.
"""
from __future__ import annotations

import json
import re
from typing import Any

import httpx

from app.tools.builtin_skills import _drafts
from app.tools.registry import register

_SAFE_METHODS = {"get"}
_NAME_RE = re.compile(r"[^a-z0-9_]+")


def _slugify(s: str) -> str:
    s = s.strip().lower().replace("-", "_").replace(" ", "_")
    s = _NAME_RE.sub("_", s)
    s = re.sub(r"_+", "_", s).strip("_")
    return s[:60] or "op"


def _params_schema(op: dict) -> dict:
    """Convert OpenAPI parameters → JSON schema for skill args."""
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
    out: dict[str, Any] = {"type": "object", "properties": props}
    if required:
        out["required"] = required
    return out


def _render_skill_code(
    *, method: str, path: str, base_url: str, parameters: list[dict], auth_header: str | None
) -> str:
    """Emit a skill body that calls the endpoint via httpx."""
    path_params = [p["name"] for p in parameters if p.get("in") == "path"]
    query_params = [p["name"] for p in parameters if p.get("in") == "query"]
    header_params = [p["name"] for p in parameters if p.get("in") == "header"]

    return f"""\
import httpx

BASE_URL = {base_url!r}
METHOD = {method.upper()!r}
PATH = {path!r}
PATH_PARAMS = {path_params!r}
QUERY_PARAMS = {query_params!r}
HEADER_PARAMS = {header_params!r}
AUTH_HEADER = {auth_header!r}

async def run(args):
    path = PATH
    for p in PATH_PARAMS:
        if p in args:
            path = path.replace("{{" + p + "}}", str(args[p]))
    url = BASE_URL.rstrip("/") + path
    params = {{k: args[k] for k in QUERY_PARAMS if k in args}}
    headers = {{k: args[k] for k in HEADER_PARAMS if k in args}}
    if AUTH_HEADER and "auth_token" in args:
        headers[AUTH_HEADER] = args["auth_token"]
    async with httpx.AsyncClient(timeout=20) as client:
        resp = await client.request(METHOD, url, params=params or None, headers=headers or None)
    body = resp.text
    if len(body) > 4000:
        body = body[:4000] + "...[truncated]"
    return {{"status": resp.status_code, "body": body}}
"""


@register(
    name="connect_http_api",
    description=(
        "Introspect an OpenAPI/Swagger spec and draft one skill per GET operation. "
        "Drafts are NOT saved until the user confirms each. Use this to connect "
        "REST APIs the user mentions (e.g. a weather API, their internal service)."
    ),
    parameters={
        "type": "object",
        "properties": {
            "openapi_url": {
                "type": "string",
                "description": "URL to the OpenAPI JSON spec (e.g. https://api.example.com/openapi.json)",
            },
            "base_url": {
                "type": "string",
                "description": "Base URL for API calls if the spec omits `servers`",
            },
            "auth_header": {
                "type": "string",
                "description": "Header name for auth token (e.g. 'Authorization'). Omit if public.",
            },
            "prefix": {
                "type": "string",
                "description": "Prefix for generated skill names, e.g. 'weather' → weather_get_forecast",
                "default": "api",
            },
            "max_ops": {
                "type": "integer",
                "default": 10,
                "minimum": 1,
                "maximum": 50,
            },
        },
        "required": ["openapi_url"],
    },
)
async def _connect(args: dict):
    url = args["openapi_url"]
    prefix = _slugify(args.get("prefix") or "api")
    max_ops = int(args.get("max_ops") or 10)
    auth_header = args.get("auth_header")

    async with httpx.AsyncClient(timeout=20) as client:
        try:
            resp = await client.get(url)
            resp.raise_for_status()
            spec = resp.json()
        except Exception as e:
            return {"ok": False, "error": f"failed to fetch spec: {e}"}

    servers = spec.get("servers") or []
    base_url = args.get("base_url") or (servers[0].get("url") if servers else None)
    if not base_url:
        return {"ok": False, "error": "no base_url (spec has no servers, none provided)"}

    drafted: list[dict] = []
    for path, ops in (spec.get("paths") or {}).items():
        if not isinstance(ops, dict):
            continue
        for method, op in ops.items():
            if method.lower() not in _SAFE_METHODS:
                continue
            if not isinstance(op, dict):
                continue
            op_id = op.get("operationId") or f"{method}_{path}"
            skill_name = f"{prefix}_{_slugify(op_id)}"[:64]
            params = op.get("parameters") or []
            schema = _params_schema(op)
            if auth_header:
                schema["properties"]["auth_token"] = {
                    "type": "string",
                    "description": f"Value for the {auth_header} header",
                }
            code = _render_skill_code(
                method=method,
                path=path,
                base_url=base_url,
                parameters=params,
                auth_header=auth_header,
            )
            _drafts[skill_name] = {
                "name": skill_name,
                "description": (op.get("summary") or op.get("description") or f"{method.upper()} {path}")[:300],
                "parameters": schema,
                "code": code,
            }
            drafted.append({"name": skill_name, "summary": op.get("summary") or path})
            if len(drafted) >= max_ops:
                break
        if len(drafted) >= max_ops:
            break

    return {
        "ok": True,
        "base_url": base_url,
        "drafts": drafted,
        "message": (
            f"Drafted {len(drafted)} skill(s) from {url}. "
            "Show the list to the user and call `confirm_skill` per name to save."
        ),
    }
