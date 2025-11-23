"""Tests for the AI model abstraction."""

from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from telegram_bot.services.ai_model import AIModel, GeminiModel, ClaudeModel, create_ai_model


class TestGeminiModel:
    """Test the GeminiModel class."""

    def test_init(self):
        """Test GeminiModel initialization."""
        with patch("telegram_bot.services.ai_model.genai.Client") as mock_client:
            model = GeminiModel(api_key="test_key", model_name="gemini-3-pro-preview")
            
            assert model.model_name == "gemini-3-pro-preview"
            mock_client.assert_called_once_with(api_key="test_key")

    @pytest.mark.asyncio
    async def test_generate_text_success(self):
        """Test successful text generation with Gemini."""
        with patch("telegram_bot.services.ai_model.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            # Mock the response
            mock_response = MagicMock()
            mock_response.text = "Generated text"
            mock_client.models.generate_content.return_value = mock_response
            
            model = GeminiModel(api_key="test_key")
            result = await model.generate_text("Test prompt")
            
            assert result == "Generated text"
            mock_client.models.generate_content.assert_called_once_with(
                model="gemini-3-pro-preview",
                contents=["Test prompt"]
            )

    @pytest.mark.asyncio
    async def test_generate_text_failure(self):
        """Test text generation failure with Gemini."""
        with patch("telegram_bot.services.ai_model.genai.Client") as mock_client_class:
            mock_client = MagicMock()
            mock_client_class.return_value = mock_client
            
            # Mock an exception
            mock_client.models.generate_content.side_effect = Exception("API Error")
            
            model = GeminiModel(api_key="test_key")
            result = await model.generate_text("Test prompt")
            
            assert result is None


class TestClaudeModel:
    """Test the ClaudeModel class."""

    def test_init(self):
        """Test ClaudeModel initialization."""
        with patch("telegram_bot.services.ai_model.AsyncAnthropic") as mock_client:
            model = ClaudeModel(api_key="test_key", model_name="claude-sonnet-4-5-20250929")
            
            assert model.model_name == "claude-sonnet-4-5-20250929"
            mock_client.assert_called_once_with(api_key="test_key")

    @pytest.mark.asyncio
    async def test_generate_text_success(self):
        """Test successful text generation with Claude."""
        with patch("telegram_bot.services.ai_model.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock the response
            mock_message = MagicMock()
            mock_message.content = [MagicMock()]
            mock_message.content[0].text = "Generated text"
            mock_client.messages.create = AsyncMock(return_value=mock_message)
            
            model = ClaudeModel(api_key="test_key")
            result = await model.generate_text("Test prompt")
            
            assert result == "Generated text"
            mock_client.messages.create.assert_called_once_with(
                model="claude-sonnet-4-5-20250929",
                max_tokens=8000,
                temperature=0.1,
                messages=[{"role": "user", "content": "Test prompt"}]
            )

    @pytest.mark.asyncio
    async def test_generate_text_failure(self):
        """Test text generation failure with Claude."""
        with patch("telegram_bot.services.ai_model.AsyncAnthropic") as mock_client_class:
            mock_client = AsyncMock()
            mock_client_class.return_value = mock_client
            
            # Mock an exception
            mock_client.messages.create.side_effect = Exception("API Error")
            
            model = ClaudeModel(api_key="test_key")
            result = await model.generate_text("Test prompt")
            
            assert result is None


class TestCreateAIModel:
    """Test the create_ai_model factory function."""

    def test_create_gemini_with_both_keys(self):
        """Test that Gemini is created when both API keys are available."""
        with patch("telegram_bot.services.ai_model.get_settings") as mock_settings:
            mock_settings.return_value.google_api_key = "google_key"
            mock_settings.return_value.anthropic_api_key = "anthropic_key"
            mock_settings.return_value.gemini_model = "gemini-3-pro-preview"
            
            with patch("telegram_bot.services.ai_model.GeminiModel") as mock_gemini:
                result = create_ai_model()
                
                mock_gemini.assert_called_once_with(
                    api_key="google_key",
                    model_name="gemini-3-pro-preview"
                )

    def test_create_gemini_with_only_google_key(self):
        """Test that Gemini is created when only Google API key is available."""
        with patch("telegram_bot.services.ai_model.get_settings") as mock_settings:
            mock_settings.return_value.google_api_key = "google_key"
            mock_settings.return_value.anthropic_api_key = ""
            mock_settings.return_value.gemini_model = "gemini-3-pro-preview"
            
            with patch("telegram_bot.services.ai_model.GeminiModel") as mock_gemini:
                result = create_ai_model()
                
                mock_gemini.assert_called_once_with(
                    api_key="google_key",
                    model_name="gemini-3-pro-preview"
                )

    def test_create_claude_with_only_anthropic_key(self):
        """Test that Claude is created when only Anthropic API key is available."""
        with patch("telegram_bot.services.ai_model.get_settings") as mock_settings:
            mock_settings.return_value.google_api_key = ""
            mock_settings.return_value.anthropic_api_key = "anthropic_key"
            mock_settings.return_value.claude_model = "claude-sonnet-4-20250514"
            
            with patch("telegram_bot.services.ai_model.ClaudeModel") as mock_claude:
                result = create_ai_model()
                
                mock_claude.assert_called_once_with(
                    api_key="anthropic_key",
                    model_name="claude-sonnet-4-20250514"
                )

    def test_create_no_keys_raises_error(self):
        """Test that ValueError is raised when no API keys are available."""
        with patch("telegram_bot.services.ai_model.get_settings") as mock_settings:
            mock_settings.return_value.google_api_key = ""
            mock_settings.return_value.anthropic_api_key = ""
            
            with pytest.raises(ValueError, match="No AI model API key provided"):
                create_ai_model() 