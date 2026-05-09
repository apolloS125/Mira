"""FastAPI application entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from telegram import Update

from app.config import settings
from app.core.database import init_db
from app.skills.registry import load_all_skills
from app.services.scheduler import get_scheduler, load_all_jobs
from app.channels.telegram import telegram_app, setup_bot_handlers
from app import tools as _tools  # noqa: F401 — registers built-in tools on import

logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("🚀 Starting Mira...")
    await init_db()
    loaded = await load_all_skills()
    logger.info(f"🧩 Loaded {loaded} user-authored skills")
    cron_loaded = await load_all_jobs()
    logger.info(f"⏰ Loaded {cron_loaded} cron jobs")
    get_scheduler().start()
    setup_bot_handlers()
    await telegram_app.initialize()
    await telegram_app.start()

    if settings.base_url and not settings.base_url.startswith("http://localhost"):
        webhook_url = f"{settings.base_url}/webhook/telegram"
        await telegram_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.telegram_webhook_secret or None,
        )
        logger.info(f"✅ Webhook set to {webhook_url}")
    else:
        logger.warning(
            "⚠️  BASE_URL not set for production. "
            "Use ngrok for local dev and set webhook manually."
        )

    yield

    logger.info("👋 Shutting down Mira...")
    get_scheduler().shutdown(wait=False)
    await telegram_app.stop()
    await telegram_app.shutdown()


app = FastAPI(
    title="Mira — Self-Evolving Personal Secretary",
    description="Telegram-first agent that authors its own Python skills and connects HTTP APIs through chat.",
    version="0.2.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    return {
        "name": "Mira",
        "version": "0.2.0",
        "status": "running",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    if settings.telegram_webhook_secret:
        token_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token_header != settings.telegram_webhook_secret:
            logger.warning("⚠️  Invalid webhook secret")
            return {"ok": False, "error": "unauthorized"}

    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        asyncio.create_task(telegram_app.process_update(update))
        return {"ok": True}
    except Exception as e:
        logger.exception(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}
