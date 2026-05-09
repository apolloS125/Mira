# 🧠 Mira — เลขาส่วนตัว AI

> *"เลขาส่วนตัวที่เขียน skills ใหม่เองได้และต่อเครื่องมือต่างๆ ผ่านแชท."*

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Latest-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Mira is a channel-agnostic AI secretary. Chat from Telegram, CLI, or any client hitting `/v1/chat`. She can **author her own Python skills** (persisted to DB, hot-loaded into the agent) and **connect new HTTP APIs from an OpenAPI spec** — all through conversation.

---

## ✨ Key Features

- 🧩 **Self-authoring skills** — Mira proposes Python tools in chat; you confirm; they're saved and callable next turn
- 🔌 **Connector wizard** — Point at an OpenAPI URL; she drafts one skill per safe operation
- ⏰ **Cron job management** — Add, list, and delete scheduled tasks through conversation
- 🔧 **Tool-calling agent loop** — LangGraph multi-step reasoning via Kimi K2 (OpenAI-compatible)
- 🌐 **Channel-agnostic** — Telegram, CLI, or anything posting to `/v1/chat`
- 🧠 **Persistent memory** — Qdrant + local multilingual embeddings; context, not a gimmick
- 🔒 **Single-owner mode** — Lock bot to one Telegram ID via `OWNER_TELEGRAM_ID`
- 🔍 **Observability** — Langfuse tracing for every LLM turn

---

## 🏗️ Architecture

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
| Channel adapters | `app/channels/` | Thin wrappers over `chat()`. Telegram + CLI |
| Chat service | `app/services/chat.py` | Resolve user, persist message, run agent, persist reply |
| Agent | `app/agents/graph.py` | LangGraph loop: `load_context → agent_loop → extract_memory` |
| Tool registry | `app/tools/registry.py` | In-memory store for built-in + user-authored tools |
| Skills registry | `app/skills/registry.py` | Compiles DB-persisted Python skills via sandboxed `exec()` |
| Scheduler | `app/services/scheduler.py` | APScheduler-backed cron job runner |
| Memory service | `app/services/memory.py` | Qdrant semantic search + LLM extraction |
| Public API | `app/api/v1/` | `/v1/chat`, `/v1/skills`, `/v1/tools` — gated by `X-API-Key` |
| Dashboard API | `app/api/dashboard.py` | Read-only REST views at `/api/*` |

---

## 🧠 Memory System

| Type | Storage | TTL | Purpose |
|------|---------|-----|---------|
| **Working** | Redis | 1 hr | Current conversation context |
| **Short-term** | PostgreSQL | 7 days | Recent messages |
| **Semantic** | Qdrant | Permanent | Facts about user |
| **Episodic** | Qdrant | Permanent | Events & experiences |
| **Procedural** | Qdrant | Permanent | Preferences & patterns |

---

## 🛠️ Tech Stack

| Layer | Tech |
|---|---|
| **Backend** | FastAPI, LangGraph, LiteLLM, SQLAlchemy |
| **LLM** | Kimi K2 via Moonshot AI (OpenAI-compatible endpoint) |
| **Databases** | PostgreSQL (pgvector), Qdrant, Redis |
| **Embeddings** | OpenAI `text-embedding-3-small` |
| **Scheduler** | APScheduler |
| **Observability** | Langfuse |
| **DevOps** | Docker, Docker Compose |

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local dev without Docker)
- Telegram Bot Token ([from @BotFather](https://t.me/botfather))
- Moonshot API Key (for Kimi K2)
- Langfuse account ([cloud.langfuse.com](https://cloud.langfuse.com)) — optional

### Setup

1. **Clone**
   ```bash
   git clone https://github.com/apolloS125/Mira.git
   cd Mira
   ```

2. **Configure**
   ```bash
   cp .env.example .env
   # Fill in TELEGRAM_BOT_TOKEN, MOONSHOT_API_KEY, OWNER_TELEGRAM_ID
   ```

3. **Local dev (SQLite, no Docker)**
   ```bash
   cd backend
   pip install -r requirements.txt
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

4. **Full stack via Docker**
   ```bash
   make up        # docker-compose up -d
   make logs      # tail backend logs
   make down      # stop
   ```

5. **Telegram webhook** (ngrok for local dev)
   ```bash
   ngrok http 8000
   curl -F "url=https://YOUR_NGROK_URL/webhook/telegram" \
        https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
   ```
   Or set `BASE_URL` in `.env` — Mira sets the webhook automatically on startup.

6. **Talk to your bot** — open Telegram, find your bot, send `/start`

---

## 📁 Project Structure

```
mira/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point + lifespan
│   │   ├── config.py            # Settings (Pydantic)
│   │   ├── channels/            # Telegram + CLI adapters
│   │   ├── agents/              # LangGraph agent loop
│   │   ├── tools/               # Built-in tools (web, http, skills, cron, time)
│   │   ├── skills/              # User-authored skill registry
│   │   ├── services/            # chat, memory, user, scheduler, embeddings
│   │   ├── models/              # SQLAlchemy ORM (User, Identity, Message, Memory, Skill, CronJob)
│   │   ├── api/                 # REST endpoints (v1 + dashboard)
│   │   ├── jobs/                # Scheduled task helpers
│   │   └── core/                # DB init, Redis client
│   ├── tests/
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/                    # Next.js 15 dashboard (Bun + Tailwind)
├── docker-compose.yml
└── .env.example
```

---

## ⚙️ Key Config Variables

| Variable | Default | Notes |
|---|---|---|
| `PRIMARY_MODEL` | `openai/kimi-k2-0711-preview` | LiteLLM model string |
| `MOONSHOT_API_KEY` | — | Required for Kimi K2 |
| `MOONSHOT_API_BASE` | `https://api.moonshot.ai/v1` | OpenAI-compatible base |
| `TELEGRAM_BOT_TOKEN` | — | Required |
| `OWNER_TELEGRAM_ID` | `0` | Set to your Telegram ID; `0` = open to all |
| `DATABASE_URL` | SQLite (local) | Switch to `postgresql+asyncpg://...` for Docker |
| `REDIS_URL` | `redis://localhost:6379/0` | |
| `QDRANT_URL` | `http://localhost:6333` | |
| `BASE_URL` | `http://localhost:8000` | Set to public URL to enable auto-webhook |
| `API_KEYS` | — | Comma-separated keys for `/v1/*` (`X-API-Key` header) |
| `LANGFUSE_PUBLIC_KEY` | `dummy` | Optional tracing |

---

## 🔒 Security

- API keys in environment variables only — never committed
- Single-owner mode via `OWNER_TELEGRAM_ID`
- Skill execution sandboxed (`exec()` with limited builtins + allowlisted imports)
- `/v1/*` API gated by `X-API-Key`

---

## 📊 Observability

LLM calls traced via Langfuse (`@observe` on `chat_with_llm`):
- Token usage & cost per turn
- Latency per agent step
- Memory retrieval performance

Set `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY` to enable. Defaults to `dummy` (disabled).

---

## 📝 License

MIT — see [LICENSE](LICENSE)

---

## 🙏 Acknowledgments

- [Moonshot AI](https://moonshot.ai) — Kimi K2 model
- [LangChain](https://langchain.com) — LangGraph framework
- [Langfuse](https://langfuse.com) — Observability platform
