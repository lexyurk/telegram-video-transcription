"""Tests for the summarization service."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_bot.services.summarization_service import SummarizationService


class TestSummarizationService:
    """Test the SummarizationService class."""

    @pytest.mark.asyncio
    async def test_create_summary_success(self):
        """Test successful summary creation."""
        # Create service with mock AI model
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = """
**Executive Summary**: This is a test summary.

**Key Points**:
- Point 1
- Point 2

**Action Items**:
- Action 1
- Action 2

**Next Steps**:
- Step 1
- Step 2
"""
        service = SummarizationService(ai_model=mock_ai_model)
        
        transcript = "Speaker 0: Hello, let's discuss the project."
        
        result = await service.create_summary_with_action_points(transcript)
        
        assert result is not None
        assert "Executive Summary" in result
        assert "Key Points" in result
        assert "Action Items" in result
        assert "Next Steps" in result
        
        # Verify the AI model was called with correct prompt
        mock_ai_model.generate_text.assert_called_once()
        call_args = mock_ai_model.generate_text.call_args[0][0]
        assert "Executive Summary" in call_args
        assert "Key Points" in call_args
        assert "Action Items" in call_args
        assert "Next Steps" in call_args
        assert transcript in call_args

    @pytest.mark.asyncio
    async def test_create_summary_ai_failure(self):
        """Test summary creation when AI model fails."""
        # Create service with mock AI model that fails
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = None
        service = SummarizationService(ai_model=mock_ai_model)
        
        transcript = "Speaker 0: Hello, let's discuss the project."
        
        result = await service.create_summary_with_action_points(transcript)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_create_summary_exception(self):
        """Test summary creation when an exception occurs."""
        # Create service with mock AI model that raises exception
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.side_effect = Exception("API Error")
        service = SummarizationService(ai_model=mock_ai_model)
        
        transcript = "Speaker 0: Hello, let's discuss the project."
        
        result = await service.create_summary_with_action_points(transcript)
        
        assert result is None

    def test_init_with_ai_model(self):
        """Test initialization with provided AI model."""
        mock_ai_model = MagicMock()
        service = SummarizationService(ai_model=mock_ai_model)
        
        assert service.ai_model == mock_ai_model

    def test_init_without_ai_model(self):
        """Test initialization without AI model (should create default)."""
        with patch("telegram_bot.services.summarization_service.create_ai_model") as mock_create:
            mock_create.side_effect = ValueError("No AI model API key provided")
            
            with pytest.raises(ValueError, match="No AI model API key provided"):
                SummarizationService() 