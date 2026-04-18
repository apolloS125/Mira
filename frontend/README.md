# Mira Dashboard

Minimal Next.js dashboard to inspect Mira users, messages, and memories.
Runs on [Bun](https://bun.sh).

## Setup

```bash
cd frontend
bun install
bun run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Config

Set `NEXT_PUBLIC_API_URL` to point at the FastAPI backend (default `http://localhost:8000`).

```bash
echo 'NEXT_PUBLIC_API_URL=http://localhost:8000' > .env.local
```
