"""Tests for speaker identification service."""

from unittest.mock import AsyncMock, patch
import pytest

from telegram_bot.speaker_identification_service import SpeakerIdentificationService


class TestSpeakerIdentificationService:
    """Test the SpeakerIdentificationService class."""

    def test_replace_speaker_labels(self):
        """Test replacing speaker labels with actual names."""
        with patch("telegram_bot.speaker_identification_service.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key = "test_key"
            service = SpeakerIdentificationService()
            
            transcript = """Speaker 0: Hello, how are you?

Speaker 1: I'm good, thanks Alexander!

Speaker 0: Great to hear that, Alexey."""
            
            speaker_names = {"0": "Alexander", "1": "Alexey"}
            
            result = service.replace_speaker_labels(transcript, speaker_names)
            
            expected = """Alexander: Hello, how are you?

Alexey: I'm good, thanks Alexander!

Alexander: Great to hear that, Alexey."""
            
            assert result == expected

    def test_replace_speaker_labels_empty_names(self):
        """Test that empty speaker names returns original transcript."""
        with patch("telegram_bot.speaker_identification_service.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key = "test_key"
            service = SpeakerIdentificationService()
            
            transcript = "Speaker 0: Hello there!"
            result = service.replace_speaker_labels(transcript, {})
            
            assert result == transcript

    def test_replace_speaker_labels_partial_names(self):
        """Test replacing only some speaker labels."""
        with patch("telegram_bot.speaker_identification_service.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key = "test_key"
            service = SpeakerIdentificationService()
            
            transcript = """Speaker 0: Hello everyone!

Speaker 1: Hi there!

Speaker 2: Good morning!"""
            
            speaker_names = {"0": "Alexander", "2": "Maria"}  # Missing speaker 1
            
            result = service.replace_speaker_labels(transcript, speaker_names)
            
            expected = """Alexander: Hello everyone!

Speaker 1: Hi there!

Maria: Good morning!"""
            
            assert result == expected

    @pytest.mark.asyncio
    async def test_identify_speakers_no_speakers(self):
        """Test identifying speakers when no speaker labels exist."""
        with patch("telegram_bot.speaker_identification_service.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key = "test_key"
            
            service = SpeakerIdentificationService()
            
            transcript = "This is just a regular text without speaker labels."
            result = await service.identify_speakers(transcript)
            
            assert result == {}

    @pytest.mark.asyncio
    async def test_process_transcript_with_speaker_names_no_speakers(self):
        """Test processing transcript when no speakers are identified."""
        with patch("telegram_bot.speaker_identification_service.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key = "test_key"
            
            service = SpeakerIdentificationService()
            
            # Mock identify_speakers to return empty dict
            with patch.object(service, 'identify_speakers', return_value={}):
                transcript = "Speaker 0: Hello there!"
                result = await service.process_transcript_with_speaker_names(transcript)
                
                # Should return original transcript when no speakers identified
                assert result == transcript

    @pytest.mark.asyncio
    async def test_process_transcript_with_speaker_names_success(self):
        """Test successful processing of transcript with speaker identification."""
        with patch("telegram_bot.speaker_identification_service.get_settings") as mock_settings:
            mock_settings.return_value.anthropic_api_key = "test_key"
            
            service = SpeakerIdentificationService()
            
            transcript = "Speaker 0: Hello, I'm Alexander!"
            speaker_names = {"0": "Alexander"}
            
            # Mock identify_speakers to return speaker names
            with patch.object(service, 'identify_speakers', return_value=speaker_names):
                result = await service.process_transcript_with_speaker_names(transcript)
                
                expected = "Alexander: Hello, I'm Alexander!"
                assert result == expected 