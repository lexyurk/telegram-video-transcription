# Telegram Video Transcription Bot Makefile

.PHONY: help install test lint format check run clean docker-build docker-run

help: ## Show this help message
	@echo 'Usage: make [target]'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  %-20s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install dependencies
	uv sync --dev

test: ## Run tests
	uv run --with pytest pytest tests/ -v

lint: ## Run linting checks
	uv run --with ruff ruff check src/ tests/
	uv run --with black black --check src/ tests/

format: ## Format code with black
	uv run --with black black src/ tests/
	uv run --with ruff ruff check src/ tests/ --fix

mypy: ## Run type checking
	uv run --with mypy mypy src/

check: lint mypy test ## Run all checks (lint, type check, test)

run: ## Run the bot
	uv run python main.py

run-backend: ## Run the Zoom FastAPI backend
	uv run uvicorn zoom_backend.app:app --host 0.0.0.0 --port 8080 --proxy-headers

clean: ## Clean up temporary files
	rm -rf temp/
	rm -rf .pytest_cache/
	rm -rf .mypy_cache/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build: ## Build Docker image
	docker build -t telegram-transcription-bot .

docker-run: ## Run in Docker (requires .env file)
	docker run --env-file .env telegram-transcription-bot

docker-compose-up: ## Run with docker-compose
	docker-compose up -d

docker-compose-down: ## Stop docker-compose services
	docker-compose down

dev-setup: install ## Set up development environment
	@echo "Development environment set up!"
	@echo "1. Copy .env.example to .env and fill in your API keys"
	@echo "2. Run 'make run' to start the bot"
	@echo "3. Run 'make test' to run tests"
	@echo "4. Run 'make check' to run all quality checks" 