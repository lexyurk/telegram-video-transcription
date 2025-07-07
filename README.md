# Telegram Video Transcription Bot

A Telegram bot that transcribes video and audio files using Deepgram AI and creates summaries with action points using AI models (Google Gemini 2.5 Flash by default, with Claude AI support).

## Features

- 🎥 **Video & Audio Transcription**: Supports multiple formats (MP4, AVI, MOV, MP3, WAV, etc.)
- 🤖 **AI-Powered**: Uses Deepgram Nova-2 for transcription and AI models for summaries (Gemini 2.5 Flash by default, Claude support available)
- 📊 **NEW: Diagram Generation**: Creates visual diagrams from transcripts using Mermaid (flowcharts, sequence diagrams, etc.)
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

## Supported File Formats

### Video
- MP4, AVI, MOV, MKV, WMV, FLV, WEBM

### Audio  
- MP3, WAV, AAC, FLAC, OGG, M4A, WMA

## How It Works

### Processing Pipeline

1. **File Upload**: Upload video/audio files up to 2GB
2. **Download**: Uses Bot API for small files (<50MB) or MTProto for large files  
3. **Transcription**: Deepgram Nova-2 with speaker diarization and smart formatting
4. **Speaker Identification**: AI analyzes conversation to identify actual speaker names
5. **Name Replacement**: Replaces "Speaker 0" with real names like "Alexander"
6. **Summarization**: AI creates summaries with action points in the same language (Gemini 2.5 Flash by default)
7. **Delivery**: Sends transcript file and formatted summary

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
- **AI Model API Key** (choose one):
  - [Google API Key](https://makersuite.google.com/app/apikey) for Gemini (default)
  - [Anthropic API Key](https://console.anthropic.com/) for Claude (alternative)

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
   
   # AI Models (at least one required)
   GOOGLE_API_KEY=your_google_key
   ANTHROPIC_API_KEY=your_anthropic_key
   
   # Optional (defaults shown)
   MAX_FILE_SIZE_MB=2048
   LOG_LEVEL=INFO
   DEEPGRAM_MODEL=nova-2
   GEMINI_MODEL=gemini-2.5-flash
   CLAUDE_MODEL=claude-sonnet-4-20250514
   ```

2. **Run with Docker Compose**:
   ```bash
   docker-compose up --build -d
   ```

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
| `GOOGLE_API_KEY` | Google API key for Gemini models (auto-detected) | Optional |
| `ANTHROPIC_API_KEY` | Anthropic API key for Claude models (auto-detected) | Optional |
| `MAX_FILE_SIZE_MB` | Maximum file size in MB | 2048 (2GB) |
| `TEMP_DIR` | Directory for temporary files | ./temp |
| `LOG_LEVEL` | Logging level (DEBUG, INFO, WARNING, ERROR) | INFO |
| `DEEPGRAM_MODEL` | Deepgram model to use | nova-2 |
| `ENABLE_DIARIZATION` | Enable speaker identification | true |
| `ENABLE_PUNCTUATION` | Enable automatic punctuation | true |
| `ENABLE_PARAGRAPHS` | Enable paragraph formatting | true |
| `ENABLE_SMART_FORMAT` | Enable smart formatting | true |
| `GEMINI_MODEL` | Gemini model to use | gemini-2.5-flash |
| `CLAUDE_MODEL` | Claude model to use | claude-sonnet-4-20250514 |

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

### 📊 Diagram Generation (NEW!)

The bot now supports creating visual diagrams from transcripts using AI and Mermaid:

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
│   │   ├── ai_model.py                   # AI model abstraction (Gemini/Claude)
│   │   ├── summarization_service.py      # AI summarization service
│   │   ├── speaker_identification_service.py # AI speaker name identification
│   │   └── file_service.py               # File operations service
│   └── mtproto_downloader.py      # Large file downloader via MTProto
├── tests/                         # Test files
├── main.py                        # Root entry point
├── pyproject.toml                 # Project configuration
├── Dockerfile                     # Docker configuration
├── .env.example                   # Environment variables template
└── README.md                      # This file
```

## API Documentation

### Deepgram
- **Website**: https://deepgram.com/
- **Docs**: https://developers.deepgram.com/
- **Models**: Nova-2 (default), Whisper, etc.

### Google Gemini (Default AI Provider)
- **Website**: https://ai.google.dev/
- **Docs**: https://ai.google.dev/docs
- **Models**: Gemini-2.5-Flash (default), Gemini-1.5-Pro, etc.

### Anthropic Claude (Alternative AI Provider)
- **Website**: https://www.anthropic.com/
- **Docs**: https://docs.anthropic.com/
- **Models**: Claude-4-Sonnet, Claude-3.5-Sonnet, Claude-3-Haiku, etc.

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

### v0.3.0
- **NEW**: 📊 **Diagram Generation Feature** - Create visual diagrams from transcripts using AI and Mermaid
- **NEW**: `/diagram` command - Reply to transcript files to generate diagrams
- **NEW**: Custom diagram prompts - Guide what the diagram should show (e.g., `/diagram show decision flow`)
- **NEW**: AI-powered diagram type selection - Automatically chooses best diagram type (flowchart, sequence, graph, etc.)
- **NEW**: Mermaid-cli integration - High-quality PNG generation with dark theme
- **NEW**: DiagramService - Clean service architecture for diagram generation
- **ADDED**: Node.js and mermaid-cli setup scripts for easy installation
- **ENHANCED**: Updated help messages and documentation with diagram examples

### v0.2.0
- **NEW**: AI Model Selection - Automatic detection between Google Gemini 2.5 Flash (priority) and Claude AI
- **NEW**: Google Gemini 2.5 Flash support with faster processing and improved quality  
- **IMPROVED**: Clean AI model abstraction with separate services architecture
- **SIMPLIFIED**: No manual model selection - automatically uses available API keys (Gemini priority)
- **ENHANCED**: Comprehensive test coverage for AI model abstraction (25+ tests)

### v0.1.0
- Initial release
- Basic transcription and summarization functionality
- Docker support
- Comprehensive logging
