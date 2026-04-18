"""Generic HTTP request tool — used by skills and connector wizard."""
import httpx

from app.tools.registry import register

ALLOWED_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE"}


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

    async with httpx.AsyncClient(timeout=float(args.get("timeout", 15))) as client:
        try:
            resp = await client.request(
                method=method,
                url=args["url"],
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
