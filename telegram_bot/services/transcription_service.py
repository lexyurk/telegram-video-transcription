"""Transcription service for handling Deepgram transcription."""

import asyncio
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
        self.timeout_seconds = settings.deepgram_timeout_seconds

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
            
            # Configure Deepgram options with speaker diarization
            options = PrerecordedOptions(
                model=settings.deepgram_model,
                detect_language=True,
                smart_format=settings.enable_smart_format,
                punctuate=settings.enable_punctuation,
                paragraphs=settings.enable_paragraphs,
                diarize=settings.enable_diarization,
                utterances=settings.enable_utterances,  # Required for speaker-labeled segments
            )

            # Read the file and create payload similar to the working example
            async with aiofiles.open(file_path, "rb") as audio_file:
                buffer_data = await audio_file.read()

            # Create payload in the format expected by Deepgram
            payload = {"buffer": buffer_data}

            logger.info(f"Starting transcription for file: {file_path} ({len(buffer_data)} bytes)")

            # Use the synchronous client wrapped in asyncio.to_thread for better compatibility
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self.client.listen.prerecorded.v("1").transcribe_file,
                    payload,
                    options
                ),
                timeout=self.timeout_seconds
            )

            logger.info("Received response from Deepgram, processing...")
            
            # Convert Deepgram response object to dict if needed
            if hasattr(response, 'to_dict'):
                response = response.to_dict()
            elif hasattr(response, '__dict__'):
                response = response.__dict__

            # Extract enhanced transcript with speaker information
            if "results" not in response:
                logger.error(f"No 'results' key in response. Available keys: {list(response.keys()) if hasattr(response, 'keys') else 'No keys'}")
                return None
                
            if not response["results"]["channels"]:
                logger.error("No channels in response results")
                return None
                
            result = response["results"]["channels"][0]["alternatives"][0]
            
            # Check if we have utterances (with speaker diarization)
            if ("utterances" in response["results"] and 
                response["results"]["utterances"] and 
                len(response["results"]["utterances"]) > 0):
                # Format transcript with speaker labels
                formatted_transcript = self._format_transcript_with_speakers(
                    response["results"]["utterances"]
                )
                logger.info(f"Found {len(response['results']['utterances'])} utterances with speaker diarization")
            else:
                # Fallback to basic transcript
                formatted_transcript = result.get("transcript", "")
                logger.info("No utterances found, using basic transcript")

            if not formatted_transcript.strip():
                logger.warning("Empty transcript received from Deepgram")
                return None

            logger.info(
                f"Successfully transcribed audio file: {len(formatted_transcript)} characters"
            )
            return formatted_transcript

        except asyncio.TimeoutError:
            logger.error(f"Transcription timed out after {self.timeout_seconds} seconds")
            return None
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
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