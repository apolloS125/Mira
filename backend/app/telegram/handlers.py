"""Telegram message and command handlers."""
import json
import logging
from io import BytesIO

from sqlalchemy import select
from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from app.agents.graph import run_agent
from app.core.database import AsyncSessionLocal
from app.models.memory import Memory
from app.models.message import Message
from app.services import memory as memory_svc
from app.services.user import get_or_create_user

logger = logging.getLogger(__name__)


# ===== Commands =====

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    async with AsyncSessionLocal() as session:
        await get_or_create_user(
            session,
            telegram_id=user.id,
            telegram_username=user.username,
            first_name=user.first_name,
            language_code=user.language_code or "th",
        )
        await session.commit()

    welcome_text = (
        f"สวัสดีค่ะคุณ {user.first_name}! 👋\n\n"
        "ฉันคือ *Mira* — AI เลขา\n\n"
        "ลองคุยกับฉันได้เลยค่ะ ฉันจะจดจำสิ่งที่คุณบอก "
        "และใช้ข้อมูลนั้นช่วยคุณในภายหลัง 🧠\n\n"
        "📝 *คำสั่งที่ใช้ได้:*\n"
        "/help - ดูคำสั่งทั้งหมด\n"
        "/memory - ดู memory ของฉัน\n"
        "/forget - ลืมเรื่องที่ต้องการ\n"
        "/export - ส่งออกข้อมูลทั้งหมด"
    )
    await update.message.reply_text(welcome_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    help_text = (
        "📚 *คำสั่งของ Mira*\n\n"
        "/start - เริ่มต้นใช้งาน\n"
        "/help - ข้อความนี้\n"
        "/memory - ดู memory ล่าสุด 10 รายการ\n"
        "/forget <เรื่อง> - ลืม memory เรื่องนั้น\n"
        "/export - ส่งออกข้อมูลทั้งหมด (JSON)\n\n"
        "💡 *Tips:*\n"
        "• ส่งข้อความธรรมดาเพื่อคุยกับฉัน\n"
        "• ส่งรูปภาพ ฉันจะช่วยวิเคราะห์ (เร็วๆ นี้)\n"
        "• Reply ข้อความเก่าเพื่อต่อ context\n"
        "• พูดภาษาไทยหรืออังกฤษก็ได้"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            telegram_id=tg_user.id,
            telegram_username=tg_user.username,
            first_name=tg_user.first_name,
        )
        await session.commit()
        user_id = user.id

    memories = await memory_svc.list_memories(user_id, limit=10)
    if not memories:
        await update.message.reply_text(
            "🧠 ยังไม่มี memory ค่ะ คุยกับฉันอีกนิดสิ",
        )
        return

    lines = ["🧠 *Memory ของคุณ*\n"]
    for i, m in enumerate(memories, 1):
        mtype = m.get("type", "?")
        content = m.get("content", "")
        lines.append(f"{i}. _({mtype})_ {content}")
    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.MARKDOWN)


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    args = context.args
    if not args:
        await update.message.reply_text(
            "ใช้งาน: /forget <เรื่องที่ต้องการลืม>\nเช่น: /forget ที่อยู่"
        )
        return

    topic = " ".join(args)
    tg_user = update.effective_user
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            telegram_id=tg_user.id,
            telegram_username=tg_user.username,
            first_name=tg_user.first_name,
        )
        await session.commit()
        user_id = user.id

    deleted = await memory_svc.delete_memories_by_topic(user_id, topic)
    if deleted:
        await update.message.reply_text(f"✅ ลืมเรื่อง '{topic}' แล้วค่ะ ({deleted} รายการ)")
    else:
        await update.message.reply_text(f"🤔 ไม่เจอ memory เกี่ยวกับ '{topic}' ค่ะ")


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    tg_user = update.effective_user
    async with AsyncSessionLocal() as session:
        user = await get_or_create_user(
            session,
            telegram_id=tg_user.id,
            telegram_username=tg_user.username,
            first_name=tg_user.first_name,
        )
        await session.commit()
        user_id = user.id

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
    message_text = update.message.text
    tg_message_id = update.message.message_id

    logger.info(f"Message from {tg_user.id} ({tg_user.username}): {message_text[:50]}...")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    try:
        async with AsyncSessionLocal() as session:
            user = await get_or_create_user(
                session,
                telegram_id=tg_user.id,
                telegram_username=tg_user.username,
                first_name=tg_user.first_name,
                language_code=tg_user.language_code or "th",
            )
            await session.flush()
            user_id = user.id
            session.add(Message(
                user_id=user_id,
                role="user",
                content=message_text,
                telegram_message_id=tg_message_id,
            ))
            await session.commit()

        reply = await run_agent(user_id=user_id, user_message=message_text)

        async with AsyncSessionLocal() as session:
            session.add(Message(user_id=user_id, role="assistant", content=reply))
            await session.commit()

        await update.message.reply_text(reply)

    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        await update.message.reply_text(
            "ขออภัยค่ะ มีข้อผิดพลาดเกิดขึ้น 😔 ลองใหม่อีกครั้งนะคะ"
        )


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )
    await update.message.reply_text(
        "📸 ได้รับรูปแล้วค่ะ — Vision feature จะพร้อมใช้งานเร็วๆ นี้"
    )
