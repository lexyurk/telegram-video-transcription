"""Configuration settings for the Telegram bot."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")
    deepgram_api_key: str = Field(alias="DEEPGRAM_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    max_file_size_mb: int = Field(default=2048, alias="MAX_FILE_SIZE_MB")
    api_id: int = Field(alias="TELEGRAM_API_ID")
    api_hash: str = Field(alias="TELEGRAM_API_HASH")

    max_processing_time_minutes: int = Field(
        default=30, alias="MAX_PROCESSING_TIME_MINUTES"
    )
    enable_file_compression: bool = Field(default=True, alias="ENABLE_FILE_COMPRESSION")

    temp_dir: str = Field(default="./temp", alias="TEMP_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    deepgram_model: str = Field(default="nova-2", alias="DEEPGRAM_MODEL")
    deepgram_timeout_seconds: int = Field(
        default=3600, alias="DEEPGRAM_TIMEOUT_SECONDS"
    )
    
    enable_diarization: bool = Field(default=True, alias="ENABLE_DIARIZATION")
    enable_punctuation: bool = Field(default=True, alias="ENABLE_PUNCTUATION")
    enable_paragraphs: bool = Field(default=True, alias="ENABLE_PARAGRAPHS")
    enable_utterances: bool = Field(default=True, alias="ENABLE_UTTERANCES")
    enable_smart_format: bool = Field(default=True, alias="ENABLE_SMART_FORMAT")
    enable_profanity_filter: bool = Field(default=False, alias="ENABLE_PROFANITY_FILTER")
    enable_redaction: bool = Field(default=False, alias="ENABLE_REDACTION")
    enable_filler_words: bool = Field(default=True, alias="ENABLE_FILLER_WORDS")

    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    claude_model: str = Field(default="claude-sonnet-4-20250514", alias="CLAUDE_MODEL")

    enable_streaming: bool = Field(default=True, alias="ENABLE_STREAMING")
    memory_limit_mb: int = Field(default=512, alias="MEMORY_LIMIT_MB")

    # Zoom integration
    zoom_client_id: str = Field(default="", alias="ZOOM_CLIENT_ID")
    zoom_client_secret: str = Field(default="", alias="ZOOM_CLIENT_SECRET")
    zoom_redirect: str = Field(default="", alias="ZOOM_REDIRECT")
    zoom_webhook_secret: str = Field(default="", alias="ZOOM_WEBHOOK_SECRET")
    state_secret: str = Field(default="", alias="STATE_SECRET")
    backend_base_url: str = Field(default="", alias="BACKEND_BASE_URL")
    zoom_db_path: str = Field(default="./temp/zoom_integration.sqlite3", alias="ZOOM_DB_PATH")


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
