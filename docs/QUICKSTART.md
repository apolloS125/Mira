# 🚀 Quick Start Guide

Get Mira running on your local machine in 15 minutes.

## Prerequisites

- Docker Desktop installed
- Python 3.11+ (optional, for local dev)
- ngrok account (free) — for Telegram webhook

## Step 1: Get API Keys

### Telegram Bot Token

1. Open Telegram, search `@BotFather`
2. Send `/newbot`
3. Choose a name (e.g., "My Mira")
4. Choose a username (must end in `bot`, e.g., `my_mira_bot`)
5. Copy the token (format: `1234:ABC-DEF...`)

### Anthropic API Key

1. Go to https://console.anthropic.com
2. Sign up / log in
3. Create an API key
4. Copy key (format: `sk-ant-...`)

### OpenAI API Key (for embeddings)

1. Go to https://platform.openai.com/api-keys
2. Create a new secret key
3. Copy key (format: `sk-...`)

### Langfuse Keys

1. Go to https://cloud.langfuse.com
2. Sign up (free tier available)
3. Create a project
4. Copy Public Key and Secret Key

## Step 2: Configure

```bash
cp .env.example .env
```

Edit `.env` and paste your keys:

```env
TELEGRAM_BOT_TOKEN=1234:ABC-DEF...
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
```

## Step 3: Start Services

```bash
docker-compose up -d
```

This starts:
- FastAPI backend (port 8000)
- PostgreSQL with pgvector (port 5432)
- Redis (port 6379)
- Qdrant vector DB (port 6333)

Check logs:
```bash
docker-compose logs -f backend
```

Verify API is up:
```bash
curl http://localhost:8000/health
# {"status":"healthy"}
```

## Step 4: Set Telegram Webhook

Telegram needs a public HTTPS URL. Use **ngrok** for local dev:

```bash
# Install ngrok: https://ngrok.com/download
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok-free.app`)

Set the webhook:

```bash
curl -F "url=https://abc123.ngrok-free.app/webhook/telegram" \
     https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook
```

You should see `{"ok":true,"result":true}`

## Step 5: Chat!

1. Open Telegram
2. Search for your bot's username
3. Send `/start`
4. Chat with Mira! 🎉

## Troubleshooting

### Bot doesn't respond

```bash
# Check webhook status
curl https://api.telegram.org/bot<TOKEN>/getWebhookInfo

# Check backend logs
docker-compose logs -f backend

# Verify .env is loaded
docker-compose exec backend env | grep TELEGRAM
```

### Database connection error

```bash
# Restart postgres
docker-compose restart postgres

# Check if ready
docker-compose exec postgres pg_isready -U mira
```

### "Module not found" errors

```bash
# Rebuild the backend
docker-compose up -d --build backend
```

## Next Steps

- Week 1-2: ✅ You're here! Basic chat works
- Week 3-5: Add memory system (see `/docs/memory-system.md`)
- Week 6-7: Multi-agent orchestration
- Week 8: Web dashboard
- Week 9-10: Deploy to production

Happy building! 🚀
