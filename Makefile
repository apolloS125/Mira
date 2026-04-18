.PHONY: help setup up down logs shell test lint clean

help:
	@echo "Mira - Personal AI Companion"
	@echo ""
	@echo "Commands:"
	@echo "  make setup     - Copy .env.example to .env"
	@echo "  make up        - Start all services"
	@echo "  make down      - Stop all services"
	@echo "  make logs      - Tail backend logs"
	@echo "  make shell     - Open shell in backend container"
	@echo "  make test      - Run tests"
	@echo "  make lint      - Run linter"
	@echo "  make clean     - Remove containers and volumes"

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "✅ Created .env — please edit it with your API keys"; \
	else \
		echo "⚠️  .env already exists"; \
	fi

up:
	docker-compose up -d
	@echo "🚀 Mira is starting..."
	@echo "   API: http://localhost:8000"
	@echo "   Health: http://localhost:8000/health"
	@echo "   Qdrant: http://localhost:6333/dashboard"

down:
	docker-compose down

logs:
	docker-compose logs -f backend

shell:
	docker-compose exec backend bash

test:
	docker-compose exec backend pytest tests/ -v

lint:
	docker-compose exec backend ruff check app/

clean:
	docker-compose down -v
	@echo "🧹 Cleaned up containers and volumes"

webhook-info:
	@echo "Checking webhook status..."
	@bash -c 'source .env && curl -s https://api.telegram.org/bot$$TELEGRAM_BOT_TOKEN/getWebhookInfo | python3 -m json.tool'

webhook-delete:
	@bash -c 'source .env && curl -s https://api.telegram.org/bot$$TELEGRAM_BOT_TOKEN/deleteWebhook'
