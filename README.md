# 🧠 Mira — Your Personal AI Companion

> *"An AI that actually remembers you"*

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)](https://fastapi.tiangolo.com)
[![LangGraph](https://img.shields.io/badge/LangGraph-Latest-orange.svg)](https://langchain-ai.github.io/langgraph/)
[![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Mira is a personal AI assistant accessible via **Telegram**, featuring a sophisticated **hierarchical memory system** that remembers you across sessions. Built with modern LLMOps practices including multi-agent orchestration, observability, and evaluation.

---

## ✨ Key Features

- 🤖 **Telegram-first UX** — Chat naturally via Telegram bot
- 🧠 **Persistent Memory** — Remembers facts, events, and preferences across sessions
- 👥 **Multi-Agent System** — Specialized agents (LangGraph)
- 📸 **Multi-modal** — Handles text and images (Claude Vision)
- 🔔 **Proactive** — Smart reminders and morning briefings
- 🔍 **Full Observability** — Langfuse tracing for every interaction
- ⚡ **Production-ready** — Docker, CI/CD, monitoring, evaluation

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
