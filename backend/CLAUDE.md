# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run the app (local)
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Run with Docker (full stack: FastAPI + PostgreSQL + Redis + Qdrant)
docker-compose up --build

# Tests
pytest
pytest tests/test_basic.py::test_import_app   # single test
pytest --cov=app --cov-report=html            # with coverage

# Lint & type check
ruff check .
ruff format .
mypy app/
```

## Architecture

Mira is a **channel-agnostic personal secretary agent** that writes its own skills and connects tools through chat. Clients (Telegram, CLI, web, anything) hand messages to a public `/v1/chat` API or the Telegram webhook; a LangGraph tool-calling loop drives the conversation, with skills and connectors as first-class extension points.

**Request flow:**
```
Client → POST /v1/chat (or /webhook/telegram) → app.services.chat.chat()
  → app.agents.graph.run_agent() → LangGraph tool-calling loop (Kimi via LiteLLM)
  → tools (web_search, http_request, propose_skill, confirm_skill, connect_http_api, user-authored skills)
  → reply delivered → messages + extracted memories persisted
```

**Infrastructure (docker-compose):**
- FastAPI (port 8000) — API server + Telegram webhook receiver
- PostgreSQL + pgvector (port 5432) — users, conversations, messages, memories
- Redis (port 6379) — working memory & caching
- Qdrant (port 6333) — vector DB for semantic memory search

**Key layers:**
- `app/api/v1/` — public headless API: `/v1/chat`, `/v1/skills`, `/v1/tools` (all gated by `X-API-Key` via `app/api/auth.py`)
- `app/channels/` — channel adapters (telegram, cli); each is a thin shell over `app.services.chat.chat()`. See `app/channels/base.py` for the contract
- `app/services/chat.py` — channel-agnostic entry: resolves user via Identity, persists message, runs agent, persists reply
- `app/services/user.py` — `get_or_create_user_by_identity(channel, external_id, …)` pattern
- `app/agents/graph.py` — LangGraph tool-calling loop (`load_context → agent_loop → extract_memory`)
- `app/tools/` — built-in tools (web_search, time_now, http_request, propose_skill, confirm_skill, create_skill, list_skills, disable_skill, list_drafts, connect_http_api) + in-memory registry
- `app/skills/registry.py` — compiles DB-persisted Python skills into Tools with a sandboxed `exec()` (limited builtins, allow-listed imports)
- `app/services/memory.py` — Qdrant + local multilingual embeddings, LLM-based extraction
- `app/models/` — SQLAlchemy ORM (User, Identity, Message, Memory, Skill)

**Notes / gotchas:**
- `app/services/llm.py` is legacy — the production path is `app.agents.graph.run_agent`. The module stays only for one-shot LLM helpers.
- Alembic migrations are not set up; `init_db()` creates tables for dev.

## Configuration

All config lives in `app/config.py` (Pydantic Settings, loaded from `.env`). Copy `.env.example` → `.env` to get started. Key settings:

- `PRIMARY_MODEL` — defaults to `claude-haiku-4-5` (LiteLLM model string)
- `DATABASE_URL` — defaults to SQLite (`sqlite+aiosqlite:///./mira.db`) for local dev; switch to PostgreSQL for Docker
- `TELEGRAM_BOT_TOKEN` — required for the bot to function
- `BASE_URL` — set to your public URL (e.g. ngrok) to enable webhook mode; omit for polling

For local dev without Docker, SQLite works out of the box. For full memory features, all four services in docker-compose are needed.

## Observability

All LLM calls are traced via Langfuse (`@observe` decorator on `chat_with_llm`). Set `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, and `LANGFUSE_HOST` to enable. Structured logging via `structlog`.

## Testing

Tests use `pytest-asyncio` with `asyncio_mode="auto"` — all async tests work without explicit `@pytest.mark.asyncio`. The test suite is minimal (basic smoke tests); integration tests will require running services.
