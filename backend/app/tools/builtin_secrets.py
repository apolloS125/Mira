"""LLM-callable secret-management tools.

Note: setting a secret value is intentionally NOT exposed as a tool. Values
must be entered via the Telegram /secret_add command so a hostile prompt-
injection cannot trick the agent into storing attacker-controlled credentials.
The agent CAN list secret names (helpful when authoring skills) and delete
secrets (after explicit user request).
"""
from app.services import secrets as secrets_svc
from app.tools.registry import register


@register(
    name="list_secrets",
    description=(
        "List the NAMES of secrets available to the current user. Values are "
        "never returned by this tool. Skills can read values via "
        "`secrets.get('NAME')`."
    ),
    parameters={"type": "object", "properties": {}},
)
async def _list_secrets(args: dict):
    from app.services.secrets import _current_user_id  # context-bound
    uid = _current_user_id.get()
    if uid is None:
        return {"ok": False, "error": "no current user context"}
    return {"ok": True, "names": await secrets_svc.list_secret_names(uid)}


@register(
    name="delete_secret",
    description=(
        "Delete a secret by name from the current user's vault. Use only when "
        "the user explicitly asks to remove a secret."
    ),
    parameters={
        "type": "object",
        "properties": {"name": {"type": "string"}},
        "required": ["name"],
    },
)
async def _delete_secret(args: dict):
    from app.services.secrets import _current_user_id
    uid = _current_user_id.get()
    if uid is None:
        return {"ok": False, "error": "no current user context"}
    ok = await secrets_svc.delete_secret(uid, args["name"])
    return {"ok": ok}
