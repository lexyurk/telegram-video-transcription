"""Tests for configuration module."""

import os
from unittest.mock import patch

import pytest

from telegram_bot.config import Settings


def test_settings_default_values():
    """Test that default values are set correctly."""
    # Mock environment variables to avoid using actual values
    with patch.dict(
        os.environ,
        {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_API_ID": "123456",
            "TELEGRAM_API_HASH": "test_hash",
            "DEEPGRAM_API_KEY": "test_deepgram",
            "ANTHROPIC_API_KEY": "test_anthropic",
        },
    ):
        settings = Settings()
        assert settings.max_file_size_mb == 2048
        assert settings.temp_dir == "./temp"
        assert settings.log_level == "INFO"
        assert settings.deepgram_model == "nova-2"
        # Language detection is now automatic
        assert settings.enable_diarization is True
        assert settings.enable_punctuation is True
        assert settings.enable_smart_format is True
        assert settings.claude_model == "claude-sonnet-4-20250514"
        assert settings.claude_max_tokens == 4000


def test_settings_required_fields():
    """Test that required fields raise ValueError when missing."""
    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises((ValueError, Exception)):
            Settings()


def test_settings_custom_values():
    """Test that custom environment values are used."""
    with patch.dict(
        os.environ,
        {
            "TELEGRAM_BOT_TOKEN": "custom_token",
            "TELEGRAM_API_ID": "123456",
            "TELEGRAM_API_HASH": "test_hash",
            "DEEPGRAM_API_KEY": "custom_deepgram",
            "ANTHROPIC_API_KEY": "custom_anthropic",
            "MAX_FILE_SIZE_MB": "100",
            "LOG_LEVEL": "DEBUG",
            "DEEPGRAM_MODEL": "whisper",
            "CLAUDE_MAX_TOKENS": "2000",
        },
    ):
        settings = Settings()
        assert settings.telegram_bot_token == "custom_token"
        assert settings.deepgram_api_key == "custom_deepgram"
        assert settings.anthropic_api_key == "custom_anthropic"
        assert settings.max_file_size_mb == 100
        assert settings.log_level == "DEBUG"
        assert settings.deepgram_model == "whisper"
        assert settings.claude_max_tokens == 2000
