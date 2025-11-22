# Telegram Video Transcription Bot

A Telegram bot that transcribes video and audio files using Deepgram AI and creates summaries with action points using AI models (Claude Sonnet 4.5 by default, with Google Gemini 2.5 Flash support).

## Features

- 🎥 **Video & Audio Transcription**: Supports multiple formats (MP4, AVI, MOV, MP3, WAV, etc.)
- 🤖 **AI-Powered**: Uses Deepgram Nova-2 for transcription and AI models for summaries (Claude Sonnet 4.5 by default, Gemini 2.5 Flash support available)
- 🔍 **NEW: RAG-Powered Search**: Ask questions across all your meetings using semantic search with ChromaDB
- 📊 **Diagram Generation**: Creates visual diagrams from transcripts using Mermaid (flowcharts, sequence diagrams, etc.)
- 💬 **Transcript Q&A**: Ask questions about individual transcript files by replying to them
- 📅 **Recording Date Tracking**: Automatically extracts and displays recording dates from video metadata
- 🌍 **Automatic Language Detection**: No need to specify language - Deepgram detects automatically
- 🎙️ **Speaker Diarization**: Identifies different speakers in conversations
- 👥 **Smart Speaker Names**: AI-powered detection of actual speaker names from conversations
- ✨ **Smart Formatting**: Automatic punctuation, paragraphs, and number formatting
- 📄 **Enhanced Transcripts**: Speaker labels, timestamps, and professional formatting
- 📝 **Smart Summaries**: Creates summaries with action points automatically
- 🚀 **Large File Support**: Handles files up to **2GB** using MTProto (Telegram's actual limit!)
- 📊 **Progress Tracking**: Real-time download progress for large files
- 🔒 **Secure**: Environment-based configuration for API keys
- 📊 **Comprehensive Logging**: Detailed logging for monitoring and debugging
- 🐳 **Docker Support**: Easy deployment with Docker containers
- 📈 **Analytics**: PostHog integration for usage tracking and insights

### 🔗 Zoom Integration (New)

Connect your Zoom account and automatically receive audio + summaries in Telegram when a cloud recording finishes.

Backend endpoints (FastAPI):
- `GET /zoom/connect?telegram_chat_id=...&telegram_user_id=...` → Zoom OAuth URL
- `GET /zoom/callback` → token exchange and mapping
- `POST /webhooks/zoom` → CRC + signature verification + recording.completed processing
- `POST /webhooks/zoom/deauth` → token cleanup on uninstall

Bot commands:
- `/connect` → deep-link to backend connect endpoint
- `/status` → basic backend reachability
- `/disconnect` → instructions for uninstall

## Supported File Formats

### Video
- MP4, AVI, MOV, MKV, WMV, FLV, WEBM

### Audio  
- MP3, WAV, AAC, FLAC, OGG, M4A, WMA

## How It Works

### Processing Pipeline

1. **File Upload**: Upload video/audio files up to 2GB
2. **Download**: Uses Bot API for small files (<50MB) or MTProto for large files
3. **Media Analysis**: Extracts recording date and duration metadata
4. **Transcription**: Deepgram Nova-2 with speaker diarization and smart formatting
5. **Speaker Identification**: AI analyzes conversation to identify actual speaker names
6. **Name Replacement**: Replaces "Speaker 0" with real names like "Alexander"
7. **Summarization**: AI creates summaries with action points in the same language (Claude Sonnet 4.5 by default)
8. **RAG Indexing**: Automatically indexes transcripts for semantic search (if enabled)
9. **Delivery**: Sends transcript file and formatted summary with recording date

### Speaker Identification

The bot includes an intelligent speaker identification system:

- **AI-Powered Name Detection**: Uses AI models to analyze conversations and identify actual speaker names
- **Automatic Replacement**: Replaces generic "Speaker 0", "Speaker 1" labels with real names
- **Context-Aware**: Analyzes how speakers address each other and introduce themselves  
- **Fallback Handling**: If names can't be identified, keeps original speaker labels
- **Multi-Language Support**: Works with conversations in any language

## Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- **Node.js 18+** and **npm** (for diagram generation)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- **Telegram API Credentials** (from [my.telegram.org](https://my.telegram.org/auth)) - Required for large file downloads
- [Deepgram API Key](https://deepgram.com/)
- **AI Model API Key** (at least one required):
  - [Anthropic API Key](https://console.anthropic.com/) for Claude Sonnet 4.5 (default, recommended)
  - [Google API Key](https://makersuite.google.com/app/apikey) for Gemini 2.5 Flash (alternative)

## Installation

### Using uv (Recommended)

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd telegram-video-transcription
   ```

2. **Install dependencies**:
   ```bash
   uv sync --dev
   ```

3. **Set up environment variables**:
   ```bash
   cp .env.example .env
   # Edit .env with your API keys
   ```

   **Getting Telegram API Credentials**:
   1. Go to [my.telegram.org](https://my.telegram.org/auth)
   2. Log in with your phone number
   3. Go to "API development tools"
   4. Create a new application
   5. Copy the `api_id` and `api_hash`

4. **Set up diagram generation** (optional but recommended):
   ```bash
   # Run the automated setup script
   ./scripts/setup_mermaid.sh
   
   # Or install manually:
   npm install -g @mermaid-js/mermaid-cli
   npx playwright install chromium
   
   # Test the installation
   python3 scripts/test_mermaid.py
   ```

5. **Run the bot**:
   ```bash
   uv run python main.py
   ```

### Using Docker

1. **Build the Docker image**:
   ```bash
   docker build -t telegram-transcription-bot .
   ```

2. **Run with environment variables**:
   ```bash
   docker run -d \
     --name transcription-bot \
     -e TELEGRAM_BOT_TOKEN=your_token \
     -e TELEGRAM_API_ID=your_api_id \
     -e TELEGRAM_API_HASH=your_api_hash \
     -e DEEPGRAM_API_KEY=your_key \
     -e GOOGLE_API_KEY=your_gemini_key \
     telegram-transcription-bot
   ```

### Using Docker Compose (Recommended)

1. **Create .env file** with your API keys:
   ```bash
   # Required
   TELEGRAM_BOT_TOKEN=your_telegram_bot_token
   TELEGRAM_API_ID=your_telegram_api_id
   TELEGRAM_API_HASH=your_telegram_api_hash
   DEEPGRAM_API_KEY=your_deepgram_key
   
   # AI Models (at least one required - Anthropic recommended)
   ANTHROPIC_API_KEY=your_anthropic_key
   GOOGLE_API_KEY=your_google_key

   # Optional (defaults shown)
   MAX_FILE_SIZE_MB=2048
   LOG_LEVEL=INFO
   DEEPGRAM_MODEL=nova-2
   CLAUDE_MODEL=claude-sonnet-4-5-20250929
   GEMINI_MODEL=gemini-3-pro

   # RAG (Retrieval Augmented Generation) for meeting search
   RAG_ENABLE_DEFAULT=false
   RAG_EMBEDDING_MODEL=text-embedding-004
   RAG_CHUNK_SIZE=400
   RAG_RETRIEVAL_K=12

   # Analytics (optional)
   POSTHOG_API_KEY=
   POSTHOG_HOST=https://app.posthog.com

    # Zoom integration
    ZOOM_CLIENT_ID=
    ZOOM_CLIENT_SECRET=
    ZOOM_REDIRECT=https://api.yourapp.com/zoom/callback
    ZOOM_WEBHOOK_SECRET=
    STATE_SECRET=
    BACKEND_BASE_URL=https://api.yourapp.com
    ZOOM_DB_PATH=./temp/zoom_integration.sqlite3
   ```

2. **Run with Docker Compose** (includes bot, backend, reverse proxy, and cert renew):
   ```bash
   docker-compose up --build -d

> **Note:** Meeting memory (RAG) now uses Gemini embeddings (`text-embedding-004`), so `GOOGLE_API_KEY` must be set even if Claude handles generation.
   ```

3. **Configure Nginx for your domain**:
   - Create config file at `./temp/nginx/api.conf` (copy from `scripts/nginx-zoom-backend.conf`)
   - Edit `server_name` to your domain (e.g., `api.yourapp.com`)
   - The reverse-proxy container loads configs from `./temp/nginx`

4. **Issue TLS certificate (first time)**:
   ```bash
   # Replace with your actual domain
   DOMAIN=api.yourapp.com
   docker run --rm \
     -v $(pwd)/temp/certs:/etc/letsencrypt \
     -v $(pwd)/temp/www:/var/www/certbot \
     certbot/certbot certonly --webroot -w /var/www/certbot -d $DOMAIN --agree-tos -m you@example.com --non-interactive
   ```
   - After success, add SSL config at `./temp/nginx/api-ssl.conf` (copy from `scripts/nginx-zoom-backend-ssl.conf`) and restart reverse proxy

3. **View logs**:
   ```bash
   docker-compose logs -f
   ```

## Configuration

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `TELEGRAM_BOT_TOKEN` | Telegram bot token from BotFather | Required |
| `TELEGRAM_API_ID` | Telegram API ID from my.telegram.org | Required |
| `TELEGRAM_API_HASH` | Telegram API Hash from my.telegram.org | Required |
| `DEEPGRAM_API_KEY` | Deepgram API key for transcription | Required |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude models (default, recommended) | At least one required |
| `GOOGLE_API_KEY` | Google API key for Gemini models (alternative) | At least one required |
| `MAX_FILE_SIZE_MB` | Maximum file size in MB | 2048 (2GB) |
| `TEMP_DIR` | Directory for temporary files | ./temp |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `DEEPGRAM_MODEL` | Deepgram model to use | nova-2 |
| `ENABLE_DIARIZATION` | Enable speaker identification | true |
| `ENABLE_PUNCTUATION` | Enable automatic punctuation | true |
| `ENABLE_PARAGRAPHS` | Enable paragraph formatting | true |
| `ENABLE_SMART_FORMAT` | Enable smart formatting | true |
| `CLAUDE_MODEL` | Claude model to use | claude-sonnet-4-5-20250929 |
| `GEMINI_MODEL` | Gemini model to use | gemini-3-pro |
| `RAG_ENABLE_DEFAULT` | Enable automatic RAG indexing for all transcripts | false |
| `RAG_EMBEDDING_MODEL` | Gemini embedding model for RAG | text-embedding-004 |
| `RAG_CHUNK_SIZE` | Size of text chunks for RAG indexing | 400 |
| `RAG_CHUNK_OVERLAP` | Overlap between chunks | 80 |
| `RAG_RETRIEVAL_K` | Number of results to retrieve | 12 |
| `RAG_SIMILARITY_THRESHOLD` | Minimum similarity score for results | 0.7 |
| `POSTHOG_API_KEY` | PostHog API key for analytics | Optional |
| `POSTHOG_HOST` | PostHog server URL | https://app.posthog.com |
| `ZOOM_CLIENT_ID` | Zoom OAuth client id | Optional |
| `ZOOM_CLIENT_SECRET` | Zoom OAuth client secret | Optional |
| `ZOOM_REDIRECT` | Zoom redirect URL (must match app) | Optional |
| `ZOOM_WEBHOOK_SECRET` | Zoom webhook secret token | Optional |
| `STATE_SECRET` | JWT secret to sign OAuth state | Optional |
| `BACKEND_BASE_URL` | Public base URL of FastAPI backend | Optional |
| `ZOOM_DB_PATH` | Path to SQLite DB for Zoom integration | ./temp/zoom_integration.sqlite3 |

### Docker services
- `telegram-bot`: the Telegram bot process
- `zoom-backend`: FastAPI backend with OAuth + webhooks
- `reverse-proxy`: Nginx proxy for backend on 80/443 with ACME webroot
- `certbot`: renews certificates periodically via webroot

## Deployment

### Website (Vercel)

The website is built with **Bun + Vite** for modern, fast frontend development with proper environment variable handling.

#### Local Development

1. **Install dependencies**:
   ```bash
   cd website
   bun install
   ```

2. **Create `.env` file** in the `website/` directory:
   ```bash
   VITE_TELEGRAM_BOT_USERNAME=@your_bot_username
   VITE_WEBSITE_URL=https://your-domain.com
   ```

3. **Run development server**:
   ```bash
   bun run dev
   ```

4. **Build for production**:
   ```bash
   bun run build
   ```

#### Vercel Deployment

1. **Push to GitHub** (if not already done):
   ```bash
   git add .
   git commit -m "Add website for deployment"
   git push
   ```

2. **Import to Vercel**:
   - Go to [vercel.com](https://vercel.com) and sign in
   - Click "New Project" and import your repository
   - Vercel will detect the Vite configuration automatically

3. **Set Environment Variables**:
   - In Vercel Dashboard → Settings → Environment Variables, add:
     - `VITE_TELEGRAM_BOT_USERNAME` = `@transcribi_bot`
     - `VITE_WEBSITE_URL` = `https://transcribiscie.app`
   
   **Note**: Vite will automatically inject these values at build time.

4. **Add Custom Domain**:
   - Go to Settings → Domains
   - Add `transcribiscie.app`
   - Update your DNS records as instructed by Vercel:
     - Add an A record pointing to Vercel's IP
     - Or add a CNAME record pointing to your Vercel project

5. **Deploy**:
   - Click "Deploy" or push to your main branch
   - Your site will be live at `https://transcribiscie.app`

#### Configuration Files

The website deployment is configured through:
- `website/package.json` - Bun dependencies and scripts
- `website/vite.config.js` - Vite build configuration
- `website/main.js` - Main JavaScript entry point
- `vercel.json` - Vercel deployment settings

#### Manual Deployment (Optional)

You can also deploy using the Vercel CLI:

```bash
npm install -g vercel
vercel --prod
```

### Telegram Bot & Backend (Docker)

The Telegram bot and Zoom backend should be deployed to a server with Docker:

1. Set up a VPS (e.g., DigitalOcean, AWS, Hetzner)
2. Configure environment variables in `.env`
3. Run with Docker Compose:
   ```bash
   docker-compose up --build -d
   ```

## Usage

1. **Start the bot** by running it with one of the methods above
2. **Find your bot** on Telegram and start a conversation
3. **Send a video or audio file** to the bot
4. **Wait for processing** - the bot will show progress updates
5. **Receive results**:
   - Transcript as a downloadable .txt file
   - Summary with action points as a formatted message

### Bot Commands

- `/start` - Show welcome message and instructions
- `/help` - Show help information
- `/diagram` - Create a diagram from a transcript (reply to a .txt file)
- `/connect` - Connect your Zoom account for automatic recording processing
- `/status` - Check Zoom integration backend status
- `/disconnect` - Disconnect your Zoom account
- **Reply to transcript files** - Ask questions about a specific transcript by replying to the .txt file

### 💬 Transcript Q&A

Ask questions about individual transcript files by simply replying to them:

1. **Get a transcript** by sending a video/audio file to the bot
2. **Reply to the transcript file** with your question
3. **Get an AI-powered answer** using Claude Sonnet 4.5

**Example Questions:**
- "What were the main action items?"
- "Who were the participants in this meeting?"
- "What was discussed about the project timeline?"
- "Summarize the key decisions made"

### 🔍 RAG-Powered Meeting Search (NEW!)

Search across all your transcripts using semantic search powered by ChromaDB and sentence transformers:

**Features:**
- 🧠 **Semantic Understanding**: Finds relevant information even if exact words don't match
- 🎯 **Contextual Answers**: Combines information from multiple meetings
- 📅 **Temporal Filtering**: Search within specific date ranges
- 🗂️ **Automatic Indexing**: All transcripts are automatically indexed (when enabled)

**Configuration:**
Set `RAG_ENABLE_DEFAULT=true` in your `.env` file to enable automatic indexing of all transcripts.

### 📊 Diagram Generation

The bot supports creating visual diagrams from transcripts using AI and Mermaid:

#### How to Use:
1. **Get a transcript** by sending a video/audio file to the bot
2. **Reply to the transcript file** with `/diagram` 
3. **Get a beautiful diagram** showing the main topics and relationships

#### Usage Examples:
- `/diagram` - Creates a generic diagram based on conversation content
- `/diagram show the decision flow` - Creates a diagram focused on decision points
- `/diagram map the relationships between people` - Creates a relationship diagram  
- `/diagram create a system architecture` - Creates a technical system diagram

#### Diagram Types:
The AI automatically chooses the best diagram type based on your content:
- **Flowcharts**: For processes, workflows, and decision trees
- **Sequence Diagrams**: For conversations and interactions between people
- **Graph Diagrams**: For relationships and connections
- **System Diagrams**: For technical architectures and components
- **Timeline Diagrams**: For chronological events

#### Features:
- 🎨 **Dark theme** with transparent background for better visibility
- 🤖 **AI-powered** diagram type selection based on content
- 🎯 **Custom prompts** to guide what the diagram should show
- 📊 **High-quality PNG images** optimized for sharing
- 🔄 **Automatic cleanup** of temporary files

## Development

### Setup Development Environment

```bash
# Install dependencies with dev tools
uv sync --dev

# Run linting
uv run ruff check src/
uv run black --check src/

# Run type checking
uv run mypy src/

# Run tests
uv run pytest
```

### Code Quality Tools

- **Black**: Code formatting
- **Ruff**: Fast Python linter
- **MyPy**: Static type checking
- **pytest**: Testing framework

### Project Structure

```
telegram-video-transcription/
├── telegram_bot/
│   ├── __init__.py
│   ├── main.py                    # Entry point
│   ├── bot.py                     # Main bot logic
│   ├── config.py                  # Configuration management
│   ├── services/                  # Services package
│   │   ├── __init__.py           # Services package init
│   │   ├── transcription_service.py      # Deepgram transcription service
│   │   ├── ai_model.py                   # AI model abstraction (Claude/Gemini)
│   │   ├── summarization_service.py      # AI summarization service
│   │   ├── speaker_identification_service.py # AI speaker name identification
│   │   ├── question_answering_service.py # Q&A service for transcripts
│   │   ├── diagram_service.py            # Diagram generation service
│   │   ├── media_info_service.py         # Media metadata extraction
│   │   ├── rag_indexing_service.py       # RAG indexing service
│   │   ├── rag_query_service.py          # RAG search service
│   │   ├── rag_storage_service.py        # RAG storage service
│   │   ├── rag_intent_parser.py          # RAG query parser
│   │   └── file_service.py               # File operations service
│   └── mtproto_downloader.py      # Large file downloader via MTProto
├── analytics.py                   # PostHog analytics integration
├── tests/                         # Test files
├── main.py                        # Root entry point
├── pyproject.toml                 # Project configuration
├── Dockerfile                     # Docker configuration
├── docker-compose.yml             # Docker Compose configuration
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

## API Documentation

### Deepgram
- **Website**: https://deepgram.com/
- **Docs**: https://developers.deepgram.com/
- **Models**: Nova-2 (default), Whisper, etc.

### Anthropic Claude (Default AI Provider)
- **Website**: https://www.anthropic.com/
- **Docs**: https://docs.anthropic.com/
- **Models**: Claude-Sonnet-4.5 (default), Claude-3.5-Sonnet, Claude-3-Haiku, etc.

### Google Gemini (Alternative AI Provider)
- **Website**: https://ai.google.dev/
- **Docs**: https://ai.google.dev/docs
- **Models**: Gemini-2.5-Flash, Gemini-1.5-Pro, etc.

### ChromaDB (Vector Database for RAG)
- **Website**: https://www.trychroma.com/
- **Docs**: https://docs.trychroma.com/
- **Purpose**: Semantic search across meeting transcripts

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests and linting
5. Submit a pull request

## License

MIT License - see LICENSE file for details.

## Support

For issues and questions:
1. Check the logs in `./temp/logs/`
2. Review the environment variables
3. Ensure API keys are valid and have sufficient credits
4. Check file format compatibility

## Changelog

### v0.5.0 (Latest)
- **NEW**: 🔍 **RAG-Powered Meeting Search** - Semantic search across all transcripts using ChromaDB
- **NEW**: 💬 **Transcript Q&A** - Ask questions about individual transcripts by replying to them
- **NEW**: 📅 **Recording Date Tracking** - Automatically extracts and displays recording dates from media
- **NEW**: 📈 **PostHog Analytics** - Track usage patterns and user behavior
- **IMPROVED**: Switched to Claude Sonnet 4.5 as default AI model (upgraded from Gemini)
- **ADDED**: RAG indexing service with automatic transcript chunking and vectorization
- **ADDED**: RAG query service with intent parsing and temporal filtering
- **ADDED**: Media info service for extracting duration and recording dates
- **ADDED**: Question answering service for individual transcript analysis
- **ENHANCED**: User tracking with Telegram ID as primary identifier
- **ENHANCED**: Analytics integration across bot and Zoom backend

### v0.4.0
- **NEW**: 🔗 **Zoom Integration** - Automatic processing of Zoom cloud recordings
- **NEW**: `/connect` command - Connect Zoom account via OAuth
- **NEW**: `/status` and `/disconnect` commands for Zoom integration
- **ADDED**: FastAPI backend for Zoom webhooks and OAuth
- **ADDED**: Docker Compose setup with reverse proxy and SSL support
- **ENHANCED**: Speaker identification improvements for Zoom recordings

### v0.3.0
- **NEW**: 📊 **Diagram Generation** - Create visual diagrams from transcripts using AI and Mermaid
- **NEW**: `/diagram` command - Reply to transcript files to generate diagrams
- **NEW**: Custom diagram prompts - Guide what the diagram should show
- **ADDED**: AI-powered diagram type selection (flowchart, sequence, graph, etc.)
- **ADDED**: Mermaid-cli integration with high-quality PNG generation
- **ADDED**: Node.js and mermaid-cli setup scripts

### v0.2.0
- **NEW**: AI Model Selection - Automatic detection between Google Gemini and Claude
- **NEW**: Google Gemini 2.5 Flash support
- **IMPROVED**: Clean AI model abstraction with separate services
- **ENHANCED**: Comprehensive test coverage for AI model abstraction

### v0.1.0
- Initial release
- Basic transcription and summarization functionality
- Speaker diarization and identification
- Docker support
- Comprehensive logging
