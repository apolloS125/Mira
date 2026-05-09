"""Generic HTTP request tool — used by skills and connector wizard."""
import ipaddress
import socket
from urllib.parse import urlparse

import httpx

from app.tools.registry import register

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}
ALLOWED_SCHEMES = {"http", "https"}


def _is_public_ip(host: str) -> bool:
    """Resolve host, reject if any address is private/loopback/link-local/multicast."""
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        return False
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            return False
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_multicast
            or ip.is_reserved
            or ip.is_unspecified
        ):
            return False
    return True


def _validate_url(url: str) -> str | None:
    """Return error string if URL unsafe, else None."""
    try:
        p = urlparse(url)
    except Exception:
        return "invalid URL"
    if p.scheme.lower() not in ALLOWED_SCHEMES:
        return f"scheme '{p.scheme}' not allowed (only http/https)"
    if not p.hostname:
        return "URL missing hostname"
    host = p.hostname.lower()
    # Block obvious aliases before DNS lookup
    if host in {"localhost", "metadata.google.internal", "metadata"}:
        return "host blocked (local/metadata)"
    if not _is_public_ip(host):
        return "host resolves to private/loopback/link-local address (SSRF blocked)"
    return None


@register(
    name="http_request",
    description=(
        "Make an HTTP request to any URL. Use for calling third-party APIs "
        "when no dedicated skill exists yet. Returns status, headers, body."
    ),
    parameters={
        "type": "object",
        "properties": {
            "url": {"type": "string", "description": "Full URL including scheme"},
            "method": {
                "type": "string",
                "enum": list(ALLOWED_METHODS),
                "default": "GET",
            },
            "headers": {
                "type": "object",
                "description": "HTTP headers as key-value",
                "additionalProperties": {"type": "string"},
            },
            "params": {
                "type": "object",
                "description": "Query parameters",
                "additionalProperties": {"type": "string"},
            },
            "json_body": {
                "type": "object",
                "description": "JSON body (for POST/PUT/PATCH)",
            },
            "timeout": {"type": "number", "default": 15},
        },
        "required": ["url"],
    },
)
async def _run(args: dict):
    method = (args.get("method") or "GET").upper()
    if method not in ALLOWED_METHODS:
        return {"error": f"method {method} not allowed"}

    url = args.get("url") or ""
    err = _validate_url(url)
    if err:
        return {"error": err}

    async with httpx.AsyncClient(
        timeout=float(args.get("timeout", 15)),
        follow_redirects=False,
    ) as client:
        try:
            resp = await client.request(
                method=method,
                url=url,
                headers=args.get("headers") or None,
                params=args.get("params") or None,
                json=args.get("json_body") or None,
            )
        except Exception as e:
            return {"error": str(e)}

    body_text = resp.text
    if len(body_text) > 4000:
        body_text = body_text[:4000] + "...[truncated]"
    return {
        "status": resp.status_code,
        "headers": dict(resp.headers),
        "body": body_text,
    }
