"""Transcription service for handling Deepgram transcription."""

import aiofiles
from deepgram import DeepgramClient, PrerecordedOptions
from loguru import logger

from telegram_bot.config import get_settings


class TranscriptionService:
    """Service for handling Deepgram transcription."""

    def __init__(self) -> None:
        """Initialize the transcription service."""
        settings = get_settings()
        self.client = DeepgramClient(settings.deepgram_api_key)

    async def transcribe_audio(self, file_path: str) -> str | None:
        """
        Transcribe audio file using Deepgram with enhanced features.

        Args:
            file_path: Path to the audio/video file

        Returns:
            Transcribed text or None if failed
        """
        try:
            settings = get_settings()
            # Configure Deepgram options with advanced features
            # Language detection is automatic - no need to specify language
            options = PrerecordedOptions(
                model=settings.deepgram_model,
                # Enable automatic language detection
                detect_language=True,
                # Advanced formatting features
                smart_format=settings.enable_smart_format,
                punctuate=settings.enable_punctuation,
                paragraphs=settings.enable_paragraphs,
                utterances=settings.enable_utterances,
                # Speaker identification
                diarize=settings.enable_diarization,
                # Additional features
                filler_words=settings.enable_filler_words,
                profanity_filter=settings.enable_profanity_filter,
                redact=settings.enable_redaction,
                # Enhanced metadata
                keywords=True,
                numerals=True,
                measurements=True,
            )

            # Read the file
            async with aiofiles.open(file_path, "rb") as audio_file:
                buffer_data = await audio_file.read()

            # Create a payload
            payload = {"buffer": buffer_data}

            # Transcribe the audio
            response = self.client.listen.prerecorded.v("1").transcribe_file(
                payload, options
            )

            # Extract enhanced transcript with speaker information
            result = response["results"]["channels"][0]["alternatives"][0]
            
            # Check if we have utterances (with speaker diarization)
            if "utterances" in response["results"] and response["results"]["utterances"]:
                # Format transcript with speaker labels
                formatted_transcript = self._format_transcript_with_speakers(
                    response["results"]["utterances"]
                )
            else:
                # Fallback to basic transcript
                formatted_transcript = result["transcript"]

            if not formatted_transcript.strip():
                logger.warning("Empty transcript received from Deepgram")
                return None

            logger.info(
                f"Successfully transcribed audio file: {len(formatted_transcript)} characters"
            )
            return formatted_transcript

        except Exception as e:
            logger.error(f"Error transcribing audio: {e}")
            return None

    def _format_transcript_with_speakers(self, utterances: list) -> str:
        """
        Format transcript with speaker labels and enhanced formatting.
        
        Args:
            utterances: List of utterances from Deepgram response
            
        Returns:
            Formatted transcript with speaker labels
        """
        formatted_lines = []
        
        for utterance in utterances:
            speaker = utterance.get("speaker", 0)
            transcript = utterance.get("transcript", "").strip()
            
            if transcript:
                # Format with speaker label
                formatted_lines.append(f"Speaker {speaker}: {transcript}")
        
        return "\n\n".join(formatted_lines)

    async def transcribe_file(self, file_path: str) -> str | None:
        """
        Transcribe file - alias for transcribe_audio for consistency.
        
        Args:
            file_path: Path to the audio/video file
            
        Returns:
            Transcribed text or None if failed
        """
        return await self.transcribe_audio(file_path) 