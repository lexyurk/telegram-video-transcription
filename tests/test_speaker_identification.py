"""Tests for speaker identification service."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from telegram_bot.services.speaker_identification_service import SpeakerIdentificationService


class TestSpeakerIdentificationService:
    """Test the SpeakerIdentificationService class."""

    def test_replace_speaker_labels(self):
        """Test replacing speaker labels with actual names."""
        # Create service with mock AI model
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = """Speaker 0: Hello there!
Speaker 1: Hi, how are you?
Speaker 0: I'm doing well, thanks."""

        speaker_names = {"0": "Alexander", "1": "Alexey"}
        
        result = service.replace_speaker_labels(transcript, speaker_names)
        
        expected = """Alexander: Hello there!
Alexey: Hi, how are you?
Alexander: I'm doing well, thanks."""
        
        assert result == expected

    def test_replace_speaker_labels_empty_names(self):
        """Test that empty speaker names returns original transcript."""
        # Create service with mock AI model
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = "Speaker 0: Hello there!"
        speaker_names = {}
        
        result = service.replace_speaker_labels(transcript, speaker_names)
        
        assert result == transcript

    def test_replace_speaker_labels_partial_names(self):
        """Test replacing only some speaker labels."""
        # Create service with mock AI model
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = """Speaker 0: Hello there!
Speaker 1: Hi, how are you?
Speaker 2: Good morning!"""

        speaker_names = {"0": "Alexander"}  # Only Speaker 0 identified
        
        result = service.replace_speaker_labels(transcript, speaker_names)
        
        expected = """Alexander: Hello there!
Speaker 1: Hi, how are you?
Speaker 2: Good morning!"""
        
        assert result == expected

    def test_replace_speaker_labels_with_disambiguated_names(self):
        """Test replacing speaker labels with disambiguated names."""
        # Create service with mock AI model
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = """Speaker 0: Hi John!
Speaker 1: Hello everyone.
Speaker 2: Good to see you John!"""

        speaker_names = {"0": "John (1)", "1": "Mary", "2": "John (2)"}
        
        result = service.replace_speaker_labels(transcript, speaker_names)
        
        expected = """John (1): Hi John!
Mary: Hello everyone.
John (2): Good to see you John!"""
        
        assert result == expected

    def test_disambiguate_speaker_names_no_duplicates(self):
        """Test disambiguation when there are no duplicate names."""
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        speaker_names = {"0": "Alexander", "1": "Mary", "2": "Bob"}
        result = service._disambiguate_speaker_names(speaker_names)
        
        # Should return original names unchanged
        assert result == speaker_names

    def test_disambiguate_speaker_names_empty_dict(self):
        """Test disambiguation with empty dictionary."""
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        speaker_names = {}
        result = service._disambiguate_speaker_names(speaker_names)
        
        assert result == {}

    def test_disambiguate_speaker_names_with_duplicates(self):
        """Test disambiguation when there are duplicate names."""
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        speaker_names = {"0": "John", "1": "Mary", "2": "John", "3": "Bob"}
        result = service._disambiguate_speaker_names(speaker_names)
        
        expected = {"0": "John (1)", "1": "Mary", "2": "John (2)", "3": "Bob"}
        assert result == expected

    def test_disambiguate_speaker_names_multiple_duplicates(self):
        """Test disambiguation with multiple sets of duplicate names."""
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        speaker_names = {"0": "John", "1": "Mary", "2": "John", "3": "Mary", "4": "Bob"}
        result = service._disambiguate_speaker_names(speaker_names)
        
        expected = {"0": "John (1)", "1": "Mary (1)", "2": "John (2)", "3": "Mary (2)", "4": "Bob"}
        assert result == expected

    def test_disambiguate_speaker_names_three_duplicates(self):
        """Test disambiguation with three speakers having the same name."""
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        speaker_names = {"0": "John", "1": "John", "2": "John"}
        result = service._disambiguate_speaker_names(speaker_names)
        
        expected = {"0": "John (1)", "1": "John (2)", "2": "John (3)"}
        assert result == expected

    @pytest.mark.asyncio
    async def test_identify_speakers_no_speakers(self):
        """Test identifying speakers when no speaker labels exist."""
        # Create service with mock AI model
        mock_ai_model = MagicMock()
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = "This is a transcript without speaker labels."
        
        result = await service.identify_speakers(transcript)
        
        assert result == {}

    @pytest.mark.asyncio
    async def test_identify_speakers_with_duplicate_names(self):
        """Test identifying speakers with duplicate names results in disambiguation."""
        # Create service with mock AI model
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = '{"0": "John", "1": "Mary", "2": "John"}'
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = """Speaker 0: Hi John!
Speaker 1: Hello everyone.
Speaker 2: Good to see you John!"""
        
        result = await service.identify_speakers(transcript)
        
        expected = {"0": "John (1)", "1": "Mary", "2": "John (2)"}
        assert result == expected

    @pytest.mark.asyncio
    async def test_process_transcript_with_speaker_names_no_speakers(self):
        """Test processing transcript when no speakers are identified."""
        # Create service with mock AI model
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = "{}"  # Empty JSON response
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = "Speaker 0: Hello there!"
        
        result = await service.process_transcript_with_speaker_names(transcript)
        
        assert result == transcript  # Should return original transcript

    @pytest.mark.asyncio
    async def test_process_transcript_with_speaker_names_success(self):
        """Test successful processing of transcript with speaker identification."""
        # Create service with mock AI model
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = '{"0": "Alexander", "1": "Alexey"}'
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = """Speaker 0: Hello Alexander!
Speaker 1: Hi Alexey, how are you?"""
        
        result = await service.process_transcript_with_speaker_names(transcript)
        
        expected = """Alexander: Hello Alexander!
Alexey: Hi Alexey, how are you?"""
        
        assert result == expected

    @pytest.mark.asyncio
    async def test_process_transcript_with_duplicate_speaker_names(self):
        """Test processing transcript with duplicate speaker names."""
        # Create service with mock AI model
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = '{"0": "John", "1": "Mary", "2": "John"}'
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = """Speaker 0: Hi everyone, I'm John from marketing.
Speaker 1: Nice to meet you, I'm Mary.
Speaker 2: Hello, I'm also John but from engineering."""
        
        result = await service.process_transcript_with_speaker_names(transcript)
        
        expected = """John (1): Hi everyone, I'm John from marketing.
Mary: Nice to meet you, I'm Mary.
John (2): Hello, I'm also John but from engineering."""
        
        assert result == expected

    @pytest.mark.asyncio
    async def test_identify_speakers_success(self):
        """Test successful speaker identification."""
        # Create service with mock AI model
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = '{"0": "Alexander", "1": "Alexey"}'
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = """Speaker 0: Hello Alexander!
Speaker 1: Hi Alexey, how are you?"""
        
        result = await service.identify_speakers(transcript)
        
        assert result == {"0": "Alexander", "1": "Alexey"}

    @pytest.mark.asyncio
    async def test_identify_speakers_invalid_json(self):
        """Test speaker identification with invalid JSON response."""
        # Create service with mock AI model
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = "Invalid JSON response"
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = "Speaker 0: Hello there!"
        
        result = await service.identify_speakers(transcript)
        
        assert result == {}

    @pytest.mark.asyncio
    async def test_identify_speakers_ai_error(self):
        """Test speaker identification when AI model fails."""
        # Create service with mock AI model
        mock_ai_model = AsyncMock()
        mock_ai_model.generate_text.return_value = None  # AI model failed
        service = SpeakerIdentificationService(ai_model=mock_ai_model)
        
        transcript = "Speaker 0: Hello there!"
        
        result = await service.identify_speakers(transcript)
        
        assert result == {} 