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

    # Anthropic API Key
    anthropic_api_key: str = Field(alias="ANTHROPIC_API_KEY")

    # File size settings
    max_file_size_mb: int = Field(default=2048, alias="MAX_FILE_SIZE_MB")  # 2GB Telegram limit
    telegram_api_limit_mb: int = Field(default=50, alias="TELEGRAM_API_LIMIT_MB")
    large_file_chunk_size_mb: int = Field(default=25, alias="LARGE_FILE_CHUNK_SIZE_MB")
    
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
        default=1800, alias="DEEPGRAM_TIMEOUT_SECONDS"
    )  # 30 minutes
    
    # Advanced Deepgram features
    enable_diarization: bool = Field(default=True, alias="ENABLE_DIARIZATION")
    enable_punctuation: bool = Field(default=True, alias="ENABLE_PUNCTUATION")
    enable_paragraphs: bool = Field(default=True, alias="ENABLE_PARAGRAPHS")
    enable_utterances: bool = Field(default=True, alias="ENABLE_UTTERANCES")
    enable_smart_format: bool = Field(default=True, alias="ENABLE_SMART_FORMAT")
    enable_profanity_filter: bool = Field(default=False, alias="ENABLE_PROFANITY_FILTER")
    enable_redaction: bool = Field(default=False, alias="ENABLE_REDACTION")
    enable_filler_words: bool = Field(default=True, alias="ENABLE_FILLER_WORDS")

    # Claude settings
    claude_model: str = Field(default="claude-sonnet-4-20250514", alias="CLAUDE_MODEL")
    claude_max_tokens: int = Field(default=4000, alias="CLAUDE_MAX_TOKENS")

    # Performance settings
    enable_streaming: bool = Field(default=True, alias="ENABLE_STREAMING")
    memory_limit_mb: int = Field(default=512, alias="MEMORY_LIMIT_MB")


def get_settings() -> Settings:
    """Get settings instance."""
    return Settings()
