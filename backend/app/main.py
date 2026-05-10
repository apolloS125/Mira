"""FastAPI application entry point."""
import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from telegram import Update

from app.config import settings
from app.core.database import init_db
from app.services.deep_memory import ensure_seeded as seed_deep_memory
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
    seed_deep_memory()
    logger.info("🧠 Deep memory ready (SOUL/IDENTITY/HEARTBEAT/USER/TOOLS/AGENT)")
    loaded = await load_all_skills()
    logger.info(f"🧩 Loaded {loaded} user-authored skills")
    cron_loaded = await load_all_jobs()
    logger.info(f"⏰ Loaded {cron_loaded} cron jobs")
    get_scheduler().start()
    setup_bot_handlers()
    await telegram_app.initialize()
    await telegram_app.start()

    is_public = settings.base_url and not settings.base_url.startswith("http://localhost")
    if is_public:
        if not settings.telegram_webhook_secret:
            raise RuntimeError(
                "TELEGRAM_WEBHOOK_SECRET is required when BASE_URL is public "
                "(ngrok / production). Without it, anyone on the internet can "
                "POST a forged Update with from.id=OWNER_TELEGRAM_ID and impersonate the owner."
            )
        webhook_url = f"{settings.base_url}/webhook/telegram"
        await telegram_app.bot.set_webhook(
            url=webhook_url,
            secret_token=settings.telegram_webhook_secret,
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
    # Fail closed: if the secret is unset (e.g. localhost dev), every request
    # is rejected with 401. Public deployments are required to set it (lifespan).
    expected = settings.telegram_webhook_secret
    if not expected:
        logger.warning("Webhook hit but TELEGRAM_WEBHOOK_SECRET is not configured")
        return Response(status_code=401)
    token_header = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if token_header != expected:
        logger.warning("Webhook invalid secret token")
        return Response(status_code=401)

    try:
        data = await request.json()
        update = Update.de_json(data, telegram_app.bot)
        asyncio.create_task(telegram_app.process_update(update))
        return {"ok": True}
    except Exception as e:
        logger.exception(f"Webhook error: {e}")
        return Response(status_code=400)
