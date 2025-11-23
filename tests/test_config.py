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
            "GOOGLE_API_KEY": "test_google",
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
        # AI model defaults
        assert settings.gemini_model == "gemini-3-pro-preview"
        assert settings.claude_model == "claude-sonnet-4-5-20250929"
        assert settings.rag_embedding_model == "text-embedding-004"
        # API keys
        assert settings.google_api_key == "test_google"
        assert settings.anthropic_api_key == ""  # Default empty


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
            "GOOGLE_API_KEY": "custom_google",
            "ANTHROPIC_API_KEY": "custom_anthropic",
            "MAX_FILE_SIZE_MB": "100",
            "LOG_LEVEL": "DEBUG",
            "DEEPGRAM_MODEL": "whisper",
            "GEMINI_MODEL": "gemini-1.5-pro",
            "CLAUDE_MODEL": "claude-3.5-sonnet",
            "RAG_EMBEDDING_MODEL": "custom-embedding-model",
        },
    ):
        settings = Settings()
        assert settings.telegram_bot_token == "custom_token"
        assert settings.deepgram_api_key == "custom_deepgram"
        assert settings.google_api_key == "custom_google"
        assert settings.anthropic_api_key == "custom_anthropic"
        assert settings.max_file_size_mb == 100
        assert settings.log_level == "DEBUG"
        assert settings.deepgram_model == "whisper"
        assert settings.gemini_model == "gemini-1.5-pro"
        assert settings.claude_model == "claude-3.5-sonnet"
        assert settings.rag_embedding_model == "custom-embedding-model"


def test_ai_model_creation_gemini_priority():
    """Test that Gemini is chosen when both API keys are provided."""
    with patch.dict(
        os.environ,
        {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_API_ID": "123456",
            "TELEGRAM_API_HASH": "test_hash",
            "DEEPGRAM_API_KEY": "test_deepgram",
            "GOOGLE_API_KEY": "test_google",
            "ANTHROPIC_API_KEY": "test_anthropic",
        },
    ):
        from telegram_bot.services.ai_model import create_ai_model, GeminiModel
        
        ai_model = create_ai_model()
        assert isinstance(ai_model, GeminiModel)


def test_ai_model_creation_claude_fallback():
    """Test that Claude is chosen when only Claude API key is provided."""
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
        from telegram_bot.services.ai_model import create_ai_model, ClaudeModel
        
        ai_model = create_ai_model()
        assert isinstance(ai_model, ClaudeModel)


def test_ai_model_creation_no_keys():
    """Test that error is raised when no AI API keys are provided."""
    with patch.dict(
        os.environ,
        {
            "TELEGRAM_BOT_TOKEN": "test_token",
            "TELEGRAM_API_ID": "123456", 
            "TELEGRAM_API_HASH": "test_hash",
            "DEEPGRAM_API_KEY": "test_deepgram",
        },
    ):
        from telegram_bot.services.ai_model import create_ai_model
        
        with pytest.raises(ValueError, match="No AI model API key provided"):
            create_ai_model()
