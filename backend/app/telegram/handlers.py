"""Telegram message and command handlers."""
import logging

from telegram import Update
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes

from app.services.llm import chat_with_llm

logger = logging.getLogger(__name__)


# ===== Commands =====

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /start command."""
    user = update.effective_user
    welcome_text = (
        f"สวัสดีค่ะคุณ {user.first_name}! 👋\n\n"
        "ฉันคือ *Mira* — AI ที่จำคุณได้จริงๆ\n\n"
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
    """Handle /help command."""
    help_text = (
        "📚 *คำสั่งของ Mira*\n\n"
        "/start - เริ่มต้นใช้งาน\n"
        "/help - ข้อความนี้\n"
        "/memory - ดู memory ล่าสุด 10 รายการ\n"
        "/forget <เรื่อง> - ลืม memory เรื่องนั้น\n"
        "/export - ส่งออกข้อมูลทั้งหมด (JSON)\n\n"
        "💡 *Tips:*\n"
        "• ส่งข้อความธรรมดาเพื่อคุยกับฉัน\n"
        "• ส่งรูปภาพ ฉันจะช่วยวิเคราะห์\n"
        "• Reply ข้อความเก่าเพื่อต่อ context\n"
        "• พูดภาษาไทยหรืออังกฤษก็ได้"
    )
    await update.message.reply_text(help_text, parse_mode=ParseMode.MARKDOWN)


async def cmd_memory(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /memory command - show recent memories."""
    # TODO: Integrate with memory service
    await update.message.reply_text(
        "🧠 *Memory ของคุณ*\n\n"
        "_ยังไม่มี memory ค่ะ คุยกับฉันอีกนิดสิ_\n\n"
        "⚙️ Feature นี้จะพร้อมใช้งานใน Week 5",
        parse_mode=ParseMode.MARKDOWN,
    )


async def cmd_forget(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /forget command."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "ใช้งาน: /forget <เรื่องที่ต้องการลืม>\n"
            "เช่น: /forget ที่อยู่"
        )
        return

    topic = " ".join(args)
    # TODO: Integrate with memory service
    await update.message.reply_text(
        f"✅ จะลืมเรื่อง '{topic}' ให้ค่ะ\n"
        "_(Feature พร้อมใช้งานใน Week 5)_",
    )


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /export command."""
    # TODO: Export user data as JSON
    await update.message.reply_text(
        "📦 กำลังเตรียมข้อมูลของคุณ...\n"
        "_(Feature พร้อมใช้งานใน Week 8)_",
    )


# ===== Message Handlers =====

async def handle_message(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle regular text messages."""
    user = update.effective_user
    message_text = update.message.text

    logger.info(f"Message from {user.id} ({user.username}): {message_text[:50]}...")

    # Show typing indicator
    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    try:
        # Simple LLM call for now (Week 1)
        # TODO Week 6: Replace with LangGraph orchestrator
        response = await chat_with_llm(
            user_id=user.id,
            message=message_text,
        )

        await update.message.reply_text(response)

    except Exception as e:
        logger.exception(f"Error handling message: {e}")
        await update.message.reply_text(
            "ขออภัยค่ะ มีข้อผิดพลาดเกิดขึ้น 😔 ลองใหม่อีกครั้งนะคะ"
        )


async def handle_photo(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
) -> None:
    """Handle photo messages."""
    user = update.effective_user
    caption = update.message.caption or "อธิบายรูปนี้ให้หน่อย"

    logger.info(f"Photo from {user.id} ({user.username})")

    await context.bot.send_chat_action(
        chat_id=update.effective_chat.id,
        action=ChatAction.TYPING,
    )

    # TODO Week 7: Integrate Claude Vision
    await update.message.reply_text(
        "📸 ได้รับรูปแล้วค่ะ\n"
        "_(Vision feature จะพร้อมใช้งานใน Week 7)_",
    )
