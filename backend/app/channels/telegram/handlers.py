"""Telegram adapter — thin shell over app.services.chat."""
import json
import logging
from io import BytesIO

from sqlalchemy import select
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from app.config import settings
from app.core.database import AsyncSessionLocal
from app.models.message import Message
from app.services import memory as memory_svc
from app.services.chat import chat as core_chat
from app.services.user import get_or_create_user_by_identity

logger = logging.getLogger(__name__)

CHANNEL = "telegram"


def _is_owner(tg_user) -> bool:
    """Return True only if sender matches configured owner. Fail closed if unset."""
    if not settings.owner_telegram_id:
        logger.error(
            "OWNER_TELEGRAM_ID not configured — rejecting all Telegram users. "
            "Set OWNER_TELEGRAM_ID in .env to your Telegram user ID."
        )
        return False
    return tg_user.id == settings.owner_telegram_id


async def _reject(update: Update) -> None:
    logger.warning(f"Rejected non-owner Telegram user {update.effective_user.id}")
    await update.message.reply_text("Sorry, this is a private assistant.")


async def _resolve_user(tg_user):
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user_by_identity(
            session,
            channel=CHANNEL,
            external_id=str(tg_user.id),
            display_name=tg_user.first_name or tg_user.username,
            language_code=tg_user.language_code or "th",
        )
        await session.commit()
        return user.id


# ===== Commands =====

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if not _is_owner(user):
        await _reject(update)
        return
    await _resolve_user(user)
    welcome_text = (
        f"สวัสดีค่ะคุณ {user.first_name}! 👋\n\n"
        "ฉันคือ *Mira* — เลขาส่วนตัว AI ของคุณ\n\n"
        "ฉันสามารถ:\n"
        "• *เขียน skill ใหม่เองได้* เมื่อคุณขอ ✨\n"
        "• *ต่อเครื่องมือ/API ใหม่ผ่านแชท* (แค่บอก URL ของ OpenAPI) 🔌\n"
        "• ค้นข้อมูลบนเว็บและเรียก API ต่างๆ 🔍\n"
        "• จำบริบทของคุณเพื่อช่วยงานได้ต่อเนื่อง 🧠\n\n"
        "ลองบอกฉันว่าคุณอยากให้ช่วยอะไร — เช่น:\n"
        "_\"ช่วยเชื่อม Gmail ให้หน่อย\"_\n"
        "_\"เรียนรู้วิธีแปลงหน่วย USD เป็น THB\"_\n\n"
        "📝 *คำสั่ง:*\n"
        "/help · /memory · /skills · /forget · /export"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    help_text = (
        "📚 *คำสั่งของ Mira*\n\n"
        "/start - เริ่มต้น\n"
        "/help - ข้อความนี้\n"
        "/memory - ดู memory ล่าสุด\n"
        "/forget <เรื่อง> - ลืมเรื่องนั้น\n"
        "/skills - ดู skill ที่มี\n"
        "/export - ส่งออกข้อมูล JSON\n\n"
        "💡 *ใช้ยังไง:*\n"
        "พิมพ์บอกฉันตรงๆ — ฉันจะเลือกใช้เครื่องมือที่เหมาะสมเอง\n"
        "หรือขอให้ฉัน *สร้าง skill ใหม่* ได้เลย"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    user_id = await _resolve_user(update.effective_user)
    memories = await memory_svc.list_memories(user_id, limit=10)
    if not memories:
        await update.message.reply_text("🧠 ยังไม่มี memory ค่ะ")
        return
    lines = ["🧠 *Memory ของคุณ*\n"]
    for i, m in enumerate(memories, 1):
        lines.append(f"{i}. _({m.get('type','?')})_ {m.get('content','')}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    args = context.args
    if not args:
        await update.message.reply_text("ใช้งาน: /forget <เรื่องที่ต้องการลืม>")
        return
    topic = " ".join(args)
    user_id = await _resolve_user(update.effective_user)
    deleted = await memory_svc.delete_memories_by_topic(user_id, topic)
    if deleted:
        await update.message.reply_text(f"✅ ลืมเรื่อง '{topic}' แล้วค่ะ ({deleted} รายการ)")
    else:
        await update.message.reply_text(f"🤔 ไม่เจอ memory เกี่ยวกับ '{topic}'")


async def cmd_skills(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    from app.skills.registry import list_skills
    skills = await list_skills()
    if not skills:
        await update.message.reply_text(
            "🔧 ยังไม่มี skill ติดตั้ง\nบอกฉันว่าอยากให้เรียนอะไร ฉันจะสร้างให้"
        )
        return
    lines = ["🔧 *Skills ที่ติดตั้ง*\n"]
    for s in skills:
        lines.append(f"• *{s['name']}* — {s['description']}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    tg_user = update.effective_user
    user_id = await _resolve_user(tg_user)
    async with AsyncSessionLocal() as session:
        msgs = (await session.execute(
            select(Message).where(Message.user_id == user_id).order_by(Message.created_at)
        )).scalars().all()
    memories = await memory_svc.list_memories(user_id, limit=500)

    payload = {
        "user": {
            "telegram_id": tg_user.id,
            "first_name": tg_user.first_name,
            "username": tg_user.username,
        },
        "messages": [
            {"role": m.role, "content": m.content, "created_at": m.created_at.isoformat()}
            for m in msgs
        ],
        "memories": memories,
    }
    buf = BytesIO(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8"))
    buf.name = "mira_export.json"
    await update.message.reply_document(document=buf, filename="mira_export.json")


# ===== Cron Commands =====

async def cmd_cron_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    # Usage: /cron_add <cron_expr> <name> | <prompt>
    # Example: /cron_add "0 9 * * *" morning | สรุปข่าวเช้า
    args = " ".join(context.args or "")
    await update.message.reply_text(
        "สร้าง cron job ผ่านแชทได้เลยค่ะ 😊 บอกฉันแบบนี้:\n\n"
        "_\"ตั้ง cron ทุกวัน 9 โมงเช้า ให้สรุปข่าวให้หน่อย\"_\n\n"
        "หรือจะพิมพ์ตรงๆ ก็ได้ค่ะ:\n"
        "`/cron_add 0 9 * * * | morning_news | สรุปข่าวเช้าวันนี้`",
        parse_mode=ParseMode.MARKDOWN,
    )
    if not args or "|" not in args:
        return
    # Parse: <cron_expr (5 fields)> | <name> | <prompt>
    try:
        parts = [p.strip() for p in args.split("|")]
        if len(parts) < 3:
            raise ValueError
        cron_parts = parts[0].split()
        if len(cron_parts) != 5:
            raise ValueError("cron must be 5 fields")
        cron_expr = " ".join(cron_parts)
        name = parts[1]
        prompt = parts[2]
    except Exception:
        await update.message.reply_text(
            "รูปแบบไม่ถูกต้องค่ะ ใช้: `/cron_add <นาที ชั่วโมง วัน เดือน วันสัปดาห์> | <ชื่อ> | <prompt>`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    user_id = await _resolve_user(update.effective_user)
    from app.models.cronjob import CronJob
    from app.services.scheduler import add_job
    job = CronJob(user_id=user_id, name=name, prompt=prompt, cron_expr=cron_expr)
    await add_job(job)
    await update.message.reply_text(
        f"✅ ตั้ง cron job *{name}* แล้วค่ะ\n"
        f"⏰ Schedule: `{cron_expr}`\n"
        f"📝 Prompt: {prompt}",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_cron_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    user_id = await _resolve_user(update.effective_user)
    from app.services.scheduler import list_jobs
    jobs = await list_jobs(user_id)
    if not jobs:
        await update.message.reply_text("⏰ ยังไม่มี cron job ค่ะ\nบอกฉันว่าอยากให้ทำอะไรตอนไหน")
        return
    lines = ["⏰ *Cron Jobs ของคุณ*\n"]
    for j in jobs:
        last = j.last_run_at.strftime("%d/%m %H:%M") if j.last_run_at else "ยังไม่เคยรัน"
        lines.append(f"• *{j.name}* — `{j.cron_expr}`\n  _{j.prompt[:60]}_\n  ID: `{str(j.id)[:8]}` | รันล่าสุด: {last}\n")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_cron_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    if not context.args:
        await update.message.reply_text("ใช้: `/cron_del <job_id>`\nดู ID ได้จาก /cron_list", parse_mode=ParseMode.MARKDOWN)
        return
    job_id_prefix = context.args[0].strip()
    user_id = await _resolve_user(update.effective_user)
    from app.services.scheduler import list_jobs, remove_job
    jobs = await list_jobs(user_id)
    match = [j for j in jobs if str(j.id).startswith(job_id_prefix)]
    if not match:
        await update.message.reply_text(f"ไม่เจอ job ID ขึ้นต้นด้วย `{job_id_prefix}` ค่ะ", parse_mode=ParseMode.MARKDOWN)
        return
    job = match[0]
    await remove_job(job.id)
    await update.message.reply_text(f"🗑️ ลบ cron job *{job.name}* แล้วค่ะ", parse_mode=ParseMode.MARKDOWN)


# ===== Message Handlers =====

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    tg_user = update.effective_user
    if not _is_owner(tg_user):
        await _reject(update)
        return
    message_text = update.message.text

    # If user is in the middle of /secret_add, treat this message as the value.
    pending_name = _pending_secrets.pop(tg_user.id, None)
    if pending_name is not None:
        from app.services.secrets import set_secret, SecretsError
        user_id = await _resolve_user(tg_user)
        try:
            await set_secret(user_id, pending_name, message_text)
        except SecretsError as e:
            await update.message.reply_text(f"❌ {e}")
            return
        # Try to delete the message containing the raw secret value.
        try:
            await update.message.delete()
        except Exception:
            pass
        await context.bot.send_message(
            chat_id=update.effective_chat.id,
            text=f"🔐 บันทึก secret `{pending_name}` แล้ว (ค่าถูกเข้ารหัส)",
            parse_mode=ParseMode.MARKDOWN,
        )
        return

    logger.info(f"Message from {tg_user.id} ({tg_user.username}): {message_text[:50]}...")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    try:
        result = await core_chat(
            channel=CHANNEL,
            external_user_id=str(tg_user.id),
            message=message_text,
            display_name=tg_user.first_name or tg_user.username,
            language_code=tg_user.language_code or "th",
        )
        await update.message.reply_text(result.reply)
    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        await update.message.reply_text(
            "ขออภัยค่ะ มีข้อผิดพลาดเกิดขึ้น 😔 ลองใหม่อีกครั้งนะคะ"
        )


# ===== Skill / Draft / Secret Commands =====

async def cmd_skill(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show source code of a skill: /skill <name>"""
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    if not context.args:
        await update.message.reply_text("ใช้: `/skill <name>`", parse_mode=ParseMode.MARKDOWN)
        return
    from app.skills.registry import get_skill
    skill = await get_skill(context.args[0].strip())
    if skill is None:
        await update.message.reply_text(f"ไม่เจอ skill `{context.args[0]}`", parse_mode=ParseMode.MARKDOWN)
        return
    header = (
        f"🔧 *{skill.name}* v{skill.version} ({skill.status})\n"
        f"_{skill.description}_\n"
    )
    body = f"```python\n{skill.code}\n```"
    if len(header) + len(body) > 3800:
        buf = BytesIO(skill.code.encode("utf-8"))
        buf.name = f"{skill.name}.py"
        await update.message.reply_text(header, parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_document(document=buf, filename=f"{skill.name}.py")
    else:
        await update.message.reply_text(header + body, parse_mode=ParseMode.MARKDOWN)


async def cmd_skill_test(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Dry-run a skill: /skill_test <name> <json_args>"""
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    if len(context.args or []) < 1:
        await update.message.reply_text(
            "ใช้: `/skill_test <name> [json_args]`",
            parse_mode=ParseMode.MARKDOWN,
        )
        return
    name = context.args[0]
    try:
        sample_args = json.loads(" ".join(context.args[1:])) if len(context.args) > 1 else {}
    except json.JSONDecodeError as e:
        await update.message.reply_text(f"JSON args ไม่ถูกต้อง: {e}")
        return

    from app.services.secrets import set_current_user, reset_current_user
    from app.skills.registry import get_skill, compile_isolated
    import time as _time

    skill = await get_skill(name)
    if skill is None:
        await update.message.reply_text(f"ไม่เจอ skill `{name}`", parse_mode=ParseMode.MARKDOWN)
        return

    user_id = await _resolve_user(update.effective_user)
    try:
        run = compile_isolated(skill)
    except Exception as e:
        await update.message.reply_text(f"❌ compile failed: {e}")
        return

    token = set_current_user(user_id)
    started = _time.monotonic()
    try:
        result = await run(sample_args)
    except Exception as e:
        result = {"ok": False, "error": f"{type(e).__name__}: {e}"}
    finally:
        reset_current_user(token)
    duration_ms = int((_time.monotonic() - started) * 1000)

    out = json.dumps(result, ensure_ascii=False, indent=2, default=str)
    if len(out) > 3500:
        out = out[:3500] + "...[truncated]"
    await update.message.reply_text(
        f"⏱ {duration_ms}ms\n```json\n{out}\n```",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_drafts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List skill drafts with inline approve/discard buttons."""
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from app.skills.registry import list_drafts
    drafts = await list_drafts()
    if not drafts:
        await update.message.reply_text("📝 ไม่มี draft รออนุมัติ")
        return
    for d in drafts:
        warn = " ⚠️" if d.get("confirmation_required") else ""
        text = f"*{d['name']}*{warn}\n_{d['description']}_"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_draft:{d['name']}"),
            InlineKeyboardButton("👁 Code", callback_data=f"show_code:{d['name']}"),
            InlineKeyboardButton("🗑 Discard", callback_data=f"discard_draft:{d['name']}"),
        ]])
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=kb)


# Pending /secret_add waits for the next message as the value.
_pending_secrets: dict[int, str] = {}


async def cmd_secret_add(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """/secret_add <name> — bot waits for next message as value."""
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    if not context.args:
        await update.message.reply_text("ใช้: `/secret_add <NAME>`", parse_mode=ParseMode.MARKDOWN)
        return
    name = context.args[0].strip()
    _pending_secrets[update.effective_user.id] = name
    await update.message.reply_text(
        f"🔐 ส่งค่าของ secret `{name}` ในข้อความถัดไป (จะลบทิ้งทันทีหลังเก็บ)",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_secret_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    from app.services.secrets import list_secret_names
    user_id = await _resolve_user(update.effective_user)
    names = await list_secret_names(user_id)
    if not names:
        await update.message.reply_text("🔐 ยังไม่มี secret\nเพิ่มด้วย `/secret_add NAME`", parse_mode=ParseMode.MARKDOWN)
        return
    body = "\n".join(f"• `{n}`" for n in names)
    await update.message.reply_text(f"🔐 *Secrets*\n{body}", parse_mode=ParseMode.MARKDOWN)


async def cmd_secret_del(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    if not context.args:
        await update.message.reply_text("ใช้: `/secret_del <NAME>`", parse_mode=ParseMode.MARKDOWN)
        return
    from app.services.secrets import delete_secret
    user_id = await _resolve_user(update.effective_user)
    ok = await delete_secret(user_id, context.args[0].strip())
    await update.message.reply_text("✅ ลบแล้ว" if ok else "❌ ไม่เจอ secret นี้")


# ===== Deep memory (identity files) =====

_MEM_FILE_BY_CMD = {
    "soul": "SOUL.md",
    "identity": "IDENTITY.md",
    "heartbeat": "HEARTBEAT.md",
    "user_md": "USER.md",
    "tools_md": "TOOLS.md",
    "agent_md": "AGENT.md",
}


async def cmd_memory_show(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Generic dump for /soul /identity /heartbeat /user_md /tools_md /agent_md."""
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    cmd = (update.message.text or "").lstrip("/").split()[0].lower()
    name = _MEM_FILE_BY_CMD.get(cmd)
    if not name:
        return
    from app.services import deep_memory as dm
    body = dm.read(name)
    await update.message.reply_text(
        f"```md\n{body}\n```",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_memory_set(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Owner-only edits for read-only files. Usage: /soul_set <full new body> ; /identity_set ..."""
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    cmd = (update.message.text or "").lstrip("/").split()[0].lower()
    mapping = {"soul_set": "SOUL.md", "identity_set": "IDENTITY.md"}
    name = mapping.get(cmd)
    if not name:
        return
    raw = update.message.text or ""
    _, _, body = raw.partition(" ")
    body = body.strip()
    if not body:
        await update.message.reply_text(f"ใช้: `/{cmd} <new content>`", parse_mode=ParseMode.MARKDOWN)
        return
    from app.services import deep_memory as dm
    try:
        await dm.write(name, body, allow_read_only=True)
        await update.message.reply_text(f"✅ {name} updated")
    except Exception as e:
        await update.message.reply_text(f"❌ {e}")


async def cmd_mem_drafts(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """List pending proposed edits to SOUL/IDENTITY with approve/discard buttons."""
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
    from app.services import deep_memory as dm
    pending = dm.list_proposed_edits()
    if not pending:
        await update.message.reply_text("ไม่มี proposed edits")
        return
    for name, body in pending.items():
        preview = body if len(body) < 1500 else body[:1500] + "…[truncated]"
        kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("✅ Approve", callback_data=f"approve_mem:{name}"),
            InlineKeyboardButton("🗑 Discard", callback_data=f"discard_mem:{name}"),
        ]])
        await update.message.reply_text(
            f"*Proposed change to {name}*\n```md\n{preview}\n```",
            parse_mode=ParseMode.MARKDOWN,
            reply_markup=kb,
        )


async def cmd_memory_list(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    from app.services import deep_memory as dm
    lines = []
    for f in dm.FILES:
        try:
            size = len(dm.read(f).encode("utf-8"))
        except Exception:
            size = 0
        lock = "🔒" if f in dm.READ_ONLY else "✏️"
        lines.append(f"{lock} *{f}* — {size}B")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    if not _is_owner(update.effective_user):
        await _reject(update)
        return
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )
    await update.message.reply_text(
        "📸 ได้รับรูปแล้วค่ะ — Vision feature เร็วๆ นี้"
    )
