# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

### Backend (Python / FastAPI)

```bash
# Local dev (SQLite, no Docker required)
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Full stack via Docker Compose (FastAPI + PostgreSQL + Redis + Qdrant)
make up          # docker-compose up -d
make down        # docker-compose down
make logs        # tail backend logs
make shell       # bash into backend container

# Tests
pytest                                          # all tests
pytest tests/test_basic.py::test_import_app    # single test
pytest --cov=app --cov-report=html             # with coverage

# Lint & format
ruff check .
ruff format .
mypy app/

# Or via Docker
make test
make lint
```

### Frontend (Next.js + Bun)

```bash
cd frontend
bun dev       # dev server on :3000
bun build
bun lint
```

### Telegram webhook

```bash
make webhook-info      # check current webhook status
make webhook-delete    # remove webhook (switches to polling)
# Set manually: curl -F "url=<ngrok-url>/webhook/telegram" \
#   https://api.telegram.org/bot<TOKEN>/setWebhook
```

## Architecture

Mira is a **channel-agnostic personal secretary agent** that can author its own Python skills and connect new HTTP APIs through conversation.

**Request flow:**
```
Client (Telegram / CLI / HTTP)
  → POST /v1/chat  OR  POST /webhook/telegram
  → app.services.chat.chat()
  → app.agents.graph.run_agent()   ← LangGraph tool-calling loop
  → tools (built-in + user-authored skills)
  → reply delivered
  → messages + memories persisted
```

**Key layers:**

| Layer | Location | Role |
|---|---|---|
| Channel adapters | `app/channels/` | Thin wrappers over `chat()`. Each implements `ChannelAdapter` in `base.py` |
| Chat service | `app/services/chat.py` | Channel-agnostic entry: resolve user, persist message, run agent, persist reply |
| Agent | `app/agents/graph.py` | LangGraph loop: `load_context → agent_loop → extract_memory` |
| Tool registry | `app/tools/registry.py` | In-memory store for built-in and user-authored tools |
| Skills registry | `app/skills/registry.py` | Compiles DB-persisted Python skills via sandboxed `exec()` (limited builtins, allow-listed imports); hot-reloaded on startup |
| Memory service | `app/services/memory.py` | Qdrant semantic search + LLM extraction |
| Cron scheduler | `app/services/scheduler.py` | APScheduler (Asia/Bangkok TZ) loads `CronJob` rows on startup, fires `run_agent()` + sends reply via Telegram to `OWNER_TELEGRAM_ID` |
| Public API | `app/api/v1/` | `/v1/chat`, `/v1/skills`, `/v1/tools` — gated by `X-API-Key` via `app/api/auth.py` |
| Dashboard API | `app/api/dashboard.py` | Read-only REST views over users/messages/memories at `/api/*` |

**Infrastructure (docker-compose):**
- FastAPI — port 8000 (API + Telegram webhook)
- PostgreSQL + pgvector — port 5432 (users, conversations, messages, memories, skills, cronjobs)
- Redis — port 6379 (working memory, caching)
- Qdrant — port 6333 (vector DB for semantic/episodic/procedural memory)

**Skill authoring flow:** The agent has two paths to save a skill:
1. `create_skill` — for trivial skills touching no user data/accounts
2. `propose_skill` → show code to user → `confirm_skill` — required when skill touches accounts or external APIs. Drafts live in-memory (`_drafts` dict in `builtin_skills.py`) and are lost on restart.

Allowed imports inside user-authored skills: `asyncio, datetime, json, math, re, statistics, textwrap, typing, urllib.parse, zoneinfo, httpx`.

**`app/telegram/` vs `app/channels/telegram/`:** There is a legacy `app/telegram/` directory. The active Telegram integration lives in `app/channels/telegram/` (bot.py + handlers.py). The legacy path can be ignored.

**`app/services/llm.py`:** Legacy one-shot LLM helper. The production path is `app.agents.graph.run_agent`. Do not add new callers to `llm.py`.

**Alembic:** Not configured. `init_db()` in `app/core/database.py` creates tables for dev. Migrations will be needed before production.

## Configuration

All settings are in `app/config.py` (Pydantic Settings). Copy `.env.example → .env`.

Key variables:
- `PRIMARY_MODEL` — LiteLLM model string, currently `openai/kimi-k2-0711-preview` (uses `MOONSHOT_API_KEY` + `MOONSHOT_API_BASE`)
- `DATABASE_URL` — defaults to SQLite for local dev; switch to `postgresql+asyncpg://...` for Docker
- `TELEGRAM_BOT_TOKEN` — required
- `OWNER_TELEGRAM_ID` — single-owner guard; set to 0 to disable (open to all)
- `BASE_URL` — set to public ngrok/production URL to enable webhook mode; omit for polling
- `API_KEYS` — comma-separated keys for the public `/v1/*` API (`X-API-Key` header)
- `LANGFUSE_PUBLIC_KEY` / `LANGFUSE_SECRET_KEY` — set to enable LLM tracing (defaults to `"dummy"`)
- `TAVILY_API_KEY` — optional; enables `web_search` tool

## Agent loop details

`app/agents/graph.py` — `MAX_STEPS = 6`. Each step: LLM call → if `tool_calls` execute tools → feed results back → repeat. Returns Thai fallback string on max-steps exceeded. All LLM calls go via `litellm.acompletion` with `api_base=MOONSHOT_API_BASE`.

## Testing

`pytest-asyncio` with `asyncio_mode="auto"` — async tests work without explicit `@pytest.mark.asyncio`. The suite is currently smoke tests only; integration tests require running services.

## Frontend

Next.js 15 App Router with Bun, TypeScript, Tailwind. Dashboard at `http://localhost:3000` talks to the backend at `http://localhost:8000/api/*`. API client is in `frontend/lib/api.ts`.
