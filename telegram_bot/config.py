"""Configuration settings for the Telegram bot."""

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    # Telegram Bot Token
    telegram_bot_token: str = Field(alias="TELEGRAM_BOT_TOKEN")

    # Deepgram API Key
    deepgram_api_key: str = Field(alias="DEEPGRAM_API_KEY")

    # AI Model API Keys (at least one required)
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")

    # File size settings
    max_file_size_mb: int = Field(default=2048, alias="MAX_FILE_SIZE_MB")  # 2GB Telegram limit
    
    # Telethon settings for large file downloads
    api_id: int = Field(alias="TELEGRAM_API_ID")
    api_hash: str = Field(alias="TELEGRAM_API_HASH")

    # Processing settings
    max_processing_time_minutes: int = Field(
        default=30, alias="MAX_PROCESSING_TIME_MINUTES"
    )
    enable_file_compression: bool = Field(default=True, alias="ENABLE_FILE_COMPRESSION")

    # Directories
    temp_dir: str = Field(default="./temp", alias="TEMP_DIR")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")

    # Deepgram settings
    deepgram_model: str = Field(default="nova-2", alias="DEEPGRAM_MODEL")
    # Language detection is automatic - no need to specify language
    deepgram_timeout_seconds: int = Field(
        default=3600, alias="DEEPGRAM_TIMEOUT_SECONDS"
    )  # 60 minutes for large files
    
    # Advanced Deepgram features - optimized for paragraph-based transcription
    enable_diarization: bool = Field(default=True, alias="ENABLE_DIARIZATION")  # Speaker identification
    enable_punctuation: bool = Field(default=True, alias="ENABLE_PUNCTUATION")  # Add punctuation
    enable_paragraphs: bool = Field(default=True, alias="ENABLE_PARAGRAPHS")  # Group into logical paragraphs
    enable_utterances: bool = Field(default=False, alias="ENABLE_UTTERANCES")  # Disabled in favor of paragraphs
    enable_smart_format: bool = Field(default=True, alias="ENABLE_SMART_FORMAT")  # Enhanced formatting
    enable_profanity_filter: bool = Field(default=False, alias="ENABLE_PROFANITY_FILTER")
    enable_redaction: bool = Field(default=False, alias="ENABLE_REDACTION")
    enable_filler_words: bool = Field(default=True, alias="ENABLE_FILLER_WORDS")  # Keep for natural flow

    # AI Model settings
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    claude_model: str = Field(default="claude-sonnet-4-20250514", alias="CLAUDE_MODEL")

    # Performance settings
    enable_streaming: bool = Field(default=True, alias="ENABLE_STREAMING")
    memory_limit_mb: int = Field(default=512, alias="MEMORY_LIMIT_MB")


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
