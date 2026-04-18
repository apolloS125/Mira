# 🧠 Mira — เลขาส่วนตัว AI

> *"เลขาส่วนตัวที่เขียน skills ใหม่เองได้และต่อเครื่องมือต่างๆ ผ่านแชท."*

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Latest-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Mira is a channel-agnostic AI secretary. Chat with her from Telegram, CLI, or any client that can hit the public `/v1/chat` API — and she can **author her own skills** (Python tools persisted to the DB and hot-loaded into the agent) and **connect new HTTP APIs from an OpenAPI spec**, all through conversation. Memory is there to make her a better assistant, not the product in itself.

---

## ✨ Key Features

- 🧩 **Self-authoring skills** — Mira proposes Python tools in chat; you confirm; they're saved and callable next turn
- 🔌 **Connector wizard** — Point her at an OpenAPI URL and she drafts one skill per safe operation
- 🔧 **Tool-calling agent loop** — LangGraph + OpenAI function-calling, multi-step reasoning
- 🌐 **Channel-agnostic** — Telegram, CLI, Web, or anything posting to `/v1/chat` (headless by design)
- 🧠 **Persistent memory** — Qdrant + local multilingual embeddings; used as context, not a gimmick
- 🔍 **Observability** — Langfuse tracing for every turn
- ⚡ **Production-ready** — Docker Compose for FastAPI + Postgres + Redis + Qdrant

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────┐
│        USER INTERFACE                        │
│           Telegram Bot                       │
└──────────────────┬──────────────────────────┘
                   │ webhook
                   ▼
┌─────────────────────────────────────────────┐
│        API GATEWAY (FastAPI)                 │
└──────────────────┬──────────────────────────┘
                   │
    ┌──────────────┼──────────────┐
    ▼              ▼              ▼
┌──────────┐  ┌─────────┐  ┌──────────────┐
│LangGraph │  │ Memory  │  │   Scheduler  │
│Orchestr. │  │ Service │  │  (Reminders) │
└─────┬────┘  └────┬────┘  └──────────────┘
      │           │
      ▼           ▼
┌──────────────────────────────┐
│  PostgreSQL + Qdrant + Redis │
└──────────────────────────────┘
              │
              ▼
┌──────────────────────────────┐
│  Langfuse (Observability)    │
└──────────────────────────────┘
```

---

## 🧠 Memory System

Mira's memory is organized hierarchically, inspired by human cognition:

| Memory Type | Storage | Purpose | Example |
|-------------|---------|---------|---------|
| **Working** | Redis | Current context (1hr TTL) | Current conversation |
| **Short-term** | PostgreSQL | Recent messages (7 days) | Yesterday's chat |
| **Semantic** | Qdrant | Facts about user | "Allergic to shrimp" |
| **Episodic** | Qdrant | Events & experiences | "Traveled to Japan last week" |
| **Procedural** | Qdrant | Preferences & patterns | "Prefers short responses" |

---

## 🛠️ Tech Stack

**Backend:** FastAPI, LangGraph, LiteLLM, Mem0, SQLAlchemy
**Databases:** PostgreSQL (pgvector), Qdrant, Redis
**AI Models:** Claude Opus 4.7 (reasoning), Claude Haiku 4.5 (routing)
**Observability:** Langfuse
**DevOps:** Docker, Docker Compose, GitHub Actions
**Deployment:** Railway / Fly.io

---

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+ (for local dev)
- Telegram Bot Token ([from @BotFather](https://t.me/botfather))
- Anthropic API Key ([console.anthropic.com](https://console.anthropic.com))
- OpenAI API Key (for embeddings)
- Langfuse account ([cloud.langfuse.com](https://cloud.langfuse.com))

### Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/apolloS125/Mira.git
   cd Mira
   ```

2. **Configure environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

3. **Start with Docker**
   ```bash
   docker-compose up -d
   ```

4. **Set up Telegram webhook** (use ngrok for local dev)
   ```bash
   ngrok http 8000
   # Copy the https URL
   curl -F "url=https://YOUR_NGROK_URL/webhook/telegram" \
        https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
   ```

5. **Talk to your bot!**
   Open Telegram, find your bot, send `/start`

---

## 📁 Project Structure

```
mira/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Settings (Pydantic)
│   │   ├── telegram/            # Telegram bot handlers
│   │   ├── agents/              # LangGraph agents
│   │   ├── services/            # Business logic
│   │   ├── models/              # SQLAlchemy models
│   │   ├── api/                 # REST endpoints
│   │   ├── jobs/                # Scheduled tasks
│   │   └── core/                # Core utilities
│   ├── tests/                   # Pytest
│   ├── alembic/                 # DB migrations
│   ├── Dockerfile
│   └── requirements.txt
├── docker-compose.yml           # Full stack
├── .env.example                 # Environment template
├── .github/workflows/           # CI/CD
└── docs/                        # Documentation
```

---

## 📊 Observability

Every LLM call is traced via Langfuse:

- Token usage & costs per user
- Latency breakdown per agent
- Memory retrieval performance
- Error tracking

Access dashboard at [cloud.langfuse.com](https://cloud.langfuse.com)

---

## 🔒 Privacy & Security

- ✅ API keys in environment variables (never committed)
- ✅ User data isolated per `telegram_id`
- ✅ `/export` command for data portability (GDPR)
- ✅ `/forget` command for memory deletion
- ✅ PII detection before memory storage

---

## 🗺️ Roadmap

- [x] Week 1-2: Foundation (FastAPI + Telegram + LLM)
- [ ] Week 3-5: Memory system (Qdrant + Mem0)
- [ ] Week 6-7: Multi-agent orchestration (LangGraph)
- [ ] Week 8: Web dashboard (Next.js)
- [ ] Week 9-10: Polish + Deploy + Documentation

---

## 📝 License

MIT License — see [LICENSE](LICENSE) file

---

## 🙏 Acknowledgments

- [Anthropic](https://anthropic.com) — Claude models
- [LangChain](https://langchain.com) — LangGraph framework
- [Mem0](https://mem0.ai) — Memory layer inspiration
- [Langfuse](https://langfuse.com) — Observability platform
