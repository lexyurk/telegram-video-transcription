"""Services for transcription and summarization."""

import os
import tempfile

import aiofiles
from anthropic import AsyncAnthropic
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


class SummarizationService:
    """Service for handling Claude AI summarization."""

    def __init__(self) -> None:
        """Initialize the summarization service."""
        settings = get_settings()
        self.client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    async def create_summary_with_action_points(self, transcript: str) -> str | None:
        """
        Create a summary with action points using Claude.

        Args:
            transcript: The transcribed text

        Returns:
            Formatted summary with action points or None if failed
        """
        try:
            prompt = f"""
Please analyze the following transcript and provide:

1. **Executive Summary**: A brief overview of the main topics discussed
2. **Key Points**: The most important information and insights
3. **Action Items**: Specific actions mentioned or implied that need to be taken
4. **Next Steps**: Recommended follow-up actions

Please format your response clearly with headers and bullet points for easy reading.

Transcript:
{transcript}
"""

            settings = get_settings()
            message = await self.client.messages.create(
                model=settings.claude_model,
                max_tokens=settings.claude_max_tokens,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )

            summary = message.content[0].text
            logger.info(f"Successfully created summary: {len(summary)} characters")
            return summary

        except Exception as e:
            logger.error(f"Error creating summary: {e}")
            return None


class FileService:
    """Service for handling file operations."""

    @staticmethod
    async def save_temp_file(file_content: bytes, file_extension: str) -> str:
        """
        Save content to a temporary file.

        Args:
            file_content: The file content as bytes
            file_extension: File extension (e.g., '.mp4', '.mp3')

        Returns:
            Path to the temporary file
        """
        # Create temp directory if it doesn't exist
        settings = get_settings()
        os.makedirs(settings.temp_dir, exist_ok=True)

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=file_extension, dir=settings.temp_dir
        ) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name

        logger.info(f"Saved temporary file: {temp_path}")
        return temp_path

    @staticmethod
    async def create_text_file(content: str, filename: str) -> str:
        """
        Create a text file with the given content.

        Args:
            content: Text content to write
            filename: Name of the file

        Returns:
            Path to the created file
        """
        # Create temp directory if it doesn't exist
        settings = get_settings()
        os.makedirs(settings.temp_dir, exist_ok=True)

        file_path = os.path.join(settings.temp_dir, filename)

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

        logger.info(f"Created text file: {file_path}")
        return file_path

    @staticmethod
    def cleanup_file(file_path: str) -> None:
        """
        Remove a temporary file.

        Args:
            file_path: Path to the file to remove
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except OSError as e:
            logger.warning(f"Failed to cleanup file {file_path}: {e}")
