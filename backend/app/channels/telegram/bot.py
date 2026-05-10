"""Telegram bot initialization and handler registration."""
import logging

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    MessageHandler,
    filters,
)

from app.config import settings
from app.channels.telegram.callbacks import callback_router
from app.channels.telegram.handlers import (
    cmd_cron_add,
    cmd_cron_del,
    cmd_cron_list,
    cmd_drafts,
    cmd_export,
    cmd_forget,
    cmd_help,
    cmd_memory,
    cmd_mem_drafts,
    cmd_memory_list,
    cmd_memory_set,
    cmd_memory_show,
    cmd_secret_add,
    cmd_secret_del,
    cmd_secret_list,
    cmd_skill,
    cmd_skill_test,
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
    telegram_app.add_handler(CommandHandler("forget", cmd_forget))
    telegram_app.add_handler(CommandHandler("export", cmd_export))

    # Skills + drafts
    telegram_app.add_handler(CommandHandler("skills", cmd_skills))
    telegram_app.add_handler(CommandHandler("skill", cmd_skill))
    telegram_app.add_handler(CommandHandler("skill_test", cmd_skill_test))
    telegram_app.add_handler(CommandHandler("drafts", cmd_drafts))

    # Secrets vault
    telegram_app.add_handler(CommandHandler("secret_add", cmd_secret_add))
    telegram_app.add_handler(CommandHandler("secret_list", cmd_secret_list))
    telegram_app.add_handler(CommandHandler("secret_del", cmd_secret_del))

    # Deep memory (identity files)
    for cmd in ("soul", "identity", "heartbeat", "user_md", "tools_md", "agent_md"):
        telegram_app.add_handler(CommandHandler(cmd, cmd_memory_show))
    telegram_app.add_handler(CommandHandler("soul_set", cmd_memory_set))
    telegram_app.add_handler(CommandHandler("identity_set", cmd_memory_set))
    telegram_app.add_handler(CommandHandler("memory_files", cmd_memory_list))
    telegram_app.add_handler(CommandHandler("mem_drafts", cmd_mem_drafts))

    # Cron
    telegram_app.add_handler(CommandHandler("cron_add", cmd_cron_add))
    telegram_app.add_handler(CommandHandler("cron_list", cmd_cron_list))
    telegram_app.add_handler(CommandHandler("cron_del", cmd_cron_del))

    # Inline-button router (must come before generic message handlers).
    telegram_app.add_handler(CallbackQueryHandler(callback_router))

    telegram_app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    telegram_app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message)
    )

    logger.info("✅ Telegram handlers registered")
