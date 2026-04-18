"""FastAPI application entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from telegram import Update

from app.api.dashboard import router as dashboard_router
from app.api.v1 import v1_router
from app.config import settings
from app.core.database import init_db
from app.skills.registry import load_all_skills
from app.channels.telegram import telegram_app, setup_bot_handlers
from app import tools as _tools  # noqa: F401 — registers built-in tools on import

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    # Startup
    logger.info("🚀 Starting Mira...")
    await init_db()
    loaded = await load_all_skills()
    logger.info(f"🧩 Loaded {loaded} user-authored skills")
    setup_bot_handlers()
    await telegram_app.initialize()
    await telegram_app.start()

    # Set webhook if BASE_URL is configured
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

    # Shutdown
    logger.info("👋 Shutting down Mira...")
    await telegram_app.stop()
    await telegram_app.shutdown()


app = FastAPI(
    title="Mira — เลขาส่วนตัว AI (Personal Secretary Agent)",
    description="เลขาส่วนตัวที่เขียน skills ใหม่เองได้และต่อเครื่องมือต่างๆ ผ่านแชท",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure properly in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(dashboard_router)
app.include_router(v1_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "Mira",
        "version": "0.1.0",
        "status": "running",
        "description": "เลขาส่วนตัว AI — เขียน skills ใหม่เองได้และต่อเครื่องมือต่างๆ ผ่านแชท",
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.post("/webhook/telegram")
async def telegram_webhook(request: Request):
    """Receive updates from Telegram."""
    # Verify webhook secret if configured
    if settings.telegram_webhook_secret:
        token_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
        if token_header != settings.telegram_webhook_secret:
            logger.warning("⚠️  Invalid webhook secret")
            return {"ok": False, "error": "unauthorized"}

    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        # Process in background so Telegram gets a fast 200 OK
        asyncio.create_task(telegram_app.process_update(update))
        return {"ok": True}
    except Exception as e:
        logger.exception(f"Webhook error: {e}")
        return {"ok": False, "error": str(e)}
