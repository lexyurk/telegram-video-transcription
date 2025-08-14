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

# Ensure .env has Zoom backend variables
if [ ! -f .env ]; then
    echo "📝 Creating .env file with required variables..."
    cat > .env <<'EOF'
TELEGRAM_BOT_TOKEN=
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
DEEPGRAM_API_KEY=
GOOGLE_API_KEY=
ANTHROPIC_API_KEY=

# Zoom integration
ZOOM_CLIENT_ID=
ZOOM_CLIENT_SECRET=
ZOOM_REDIRECT=https://api.yourapp.com/zoom/callback
ZOOM_WEBHOOK_SECRET=
STATE_SECRET=
BACKEND_BASE_URL=https://api.yourapp.com
ZOOM_DB_PATH=./temp/zoom_integration.sqlite3
EOF
else
    echo "✅ .env file already exists — ensure Zoom vars are present (ZOOM_CLIENT_ID, etc.)"
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