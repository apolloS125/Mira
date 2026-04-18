"""Telegram bot initialization and handler registration."""
import logging

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import settings
from app.channels.telegram.handlers import (
    cmd_export,
    cmd_forget,
    cmd_help,
    cmd_memory,
    cmd_skills,
    cmd_start,
    handle_message,
    handle_photo,
)

logger = logging.getLogger(__name__)

telegram_app: Application = (
    Application.builder()
    .token(settings.telegram_bot_token)
    .build()
)


def setup_bot_handlers() -> None:
    """Register all bot handlers."""
    telegram_app.add_handler(CommandHandler("start", cmd_start))
    telegram_app.add_handler(CommandHandler("help", cmd_help))
    telegram_app.add_handler(CommandHandler("memory", cmd_memory))
    telegram_app.add_handler(CommandHandler("skills", cmd_skills))
    telegram_app.add_handler(CommandHandler("forget", cmd_forget))
    telegram_app.add_handler(CommandHandler("export", cmd_export))

    telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    telegram_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("✅ Telegram handlers registered")
