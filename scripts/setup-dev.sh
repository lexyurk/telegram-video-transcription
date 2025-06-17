#!/bin/bash
# Development setup script for Telegram Video Transcription Bot

set -e

echo "🤖 Setting up Telegram Video Transcription Bot development environment..."

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo "❌ uv is not installed. Please install it first: https://docs.astral.sh/uv/"
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
uv sync --dev

# Create .env file if it doesn't exist
if [ ! -f .env ]; then
    echo "📝 Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  Please edit .env file and add your API keys:"
    echo "   - TELEGRAM_BOT_TOKEN"
    echo "   - DEEPGRAM_API_KEY"
    echo "   - ANTHROPIC_API_KEY"
else
    echo "✅ .env file already exists"
fi

# Create temp directory
echo "📁 Creating temp directory..."
mkdir -p temp

# Run tests to make sure everything works
echo "🧪 Running tests..."
uv run pytest tests/ -v

# Run linting
echo "🔍 Running linting checks..."
uv run ruff check src/ tests/
uv run black --check src/ tests/

echo ""
echo "🎉 Development environment setup complete!"
echo ""
echo "Next steps:"
echo "1. Edit .env file with your API keys"
echo "2. Run: make run (or uv run python main.py)"
echo "3. Send a video/audio file to your bot on Telegram"
echo ""
echo "Available commands:"
echo "  make help     - Show available commands"
echo "  make test     - Run tests"
echo "  make lint     - Run linting"
echo "  make format   - Format code"
echo "  make check    - Run all checks"
echo "  make run      - Start the bot" 