"""Inline-button callback router.

Confirming a draft is intentionally only reachable from a Telegram callback
query (i.e. the user pressed an inline button). The agent itself cannot promote
drafts — this defeats prompt-injection attempts where a malicious payload
tells the agent "now confirm skill X".
"""
import logging
from io import BytesIO

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.config import settings

logger = logging.getLogger(__name__)


def _is_owner(tg_user) -> bool:
    if not settings.owner_telegram_id:
        return False
    return tg_user.id == settings.owner_telegram_id


async def callback_router(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    if query is None:
        return
    if not _is_owner(update.effective_user):
        await query.answer("Not authorized.", show_alert=True)
        return

    data = query.data or ""
    action, _, arg = data.partition(":")

    if action == "approve_draft":
        from app.skills.registry import confirm_draft
        skill = await confirm_draft(arg)
        if skill is None:
            await query.answer("Draft not found.", show_alert=True)
            return
        await query.answer("✅ Approved")
        await query.edit_message_text(
            f"✅ *{skill.name}* v{skill.version} active",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    if action == "discard_draft":
        from app.skills.registry import discard_draft
        ok = await discard_draft(arg)
        await query.answer("🗑 Discarded" if ok else "Not found", show_alert=not ok)
        if ok:
            await query.edit_message_text(f"🗑 Discarded *{arg}*", parse_mode=ParseMode.MARKDOWN)
        return

    if action == "show_code":
        from app.skills.registry import get_skill
        skill = await get_skill(arg)
        if skill is None:
            await query.answer("Not found.", show_alert=True)
            return
        await query.answer()
        body = f"```python\n{skill.code}\n```"
        if len(body) > 3800:
            buf = BytesIO(skill.code.encode("utf-8"))
            buf.name = f"{skill.name}.py"
            await query.message.reply_document(document=buf, filename=f"{skill.name}.py")
        else:
            await query.message.reply_text(body, parse_mode=ParseMode.MARKDOWN)
        return

    if action == "disable_skill":
        from app.skills.registry import disable_skill
        ok = await disable_skill(arg)
        await query.answer("Disabled" if ok else "Not found", show_alert=not ok)
        return

    await query.answer(f"Unknown action: {action}", show_alert=True)
