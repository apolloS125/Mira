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
    """Return True if the sender is the configured owner, or if guard is disabled."""
    if settings.owner_telegram_id == 0:
        return True
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
