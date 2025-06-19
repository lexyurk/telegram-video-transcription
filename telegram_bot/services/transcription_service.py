"""Transcription service for handling Deepgram transcription."""

import asyncio
import aiofiles
from deepgram import DeepgramClient, PrerecordedOptions
from loguru import logger

from telegram_bot.config import get_settings


class TranscriptionService:
    """Service for handling Deepgram transcription with advanced features."""

    def __init__(self) -> None:
        """Initialize the transcription service."""
        settings = get_settings()
        self.client = DeepgramClient(settings.deepgram_api_key)
        self.timeout_seconds = settings.deepgram_timeout_seconds

    async def transcribe_audio(self, file_path: str) -> str | None:
        """
        Transcribe audio file using Deepgram with enhanced features.
        Uses paragraphs instead of utterances for better content grouping.

        Args:
            file_path: Path to the audio/video file

        Returns:
            Transcribed text or None if failed
        """
        try:
            settings = get_settings()
            
            # Configure Deepgram options with optimal settings
            options = PrerecordedOptions(
                model=settings.deepgram_model,
                # Language detection and formatting
                detect_language=True,  # Auto-detect language
                smart_format=settings.enable_smart_format,  # Better formatting (dates, numbers, etc.)
                punctuate=settings.enable_punctuation,  # Add punctuation
                
                # Content structure - use both paragraphs and utterances
                paragraphs=settings.enable_paragraphs,  # Group content into logical paragraphs
                utterances=True,  # Keep as fallback for speaker diarization
                
                # Speaker identification
                diarize=settings.enable_diarization,  # Enable speaker identification
                
                # Audio processing enhancements
                filler_words=settings.enable_filler_words,  # Include filler words for natural flow
                profanity_filter=settings.enable_profanity_filter,
                redact=settings.enable_redaction,
                
                # Output formatting
                encoding="linear16",  # Ensure consistent audio processing
                sample_rate=16000,  # Standard sample rate for best results
            )

            # Read the file and create payload
            async with aiofiles.open(file_path, "rb") as audio_file:
                buffer_data = await audio_file.read()

            payload = {"buffer": buffer_data}

            logger.info(f"Starting enhanced transcription for file: {file_path} ({len(buffer_data)} bytes)")
            logger.info(f"Features enabled: diarization={settings.enable_diarization}, smart_format={settings.enable_smart_format}, paragraphs={settings.enable_paragraphs}")

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

            # Extract enhanced transcript
            if "results" not in response:
                logger.error(f"No 'results' key in response. Available keys: {list(response.keys()) if hasattr(response, 'keys') else 'No keys'}")
                return None
                
            if not response["results"]["channels"]:
                logger.error("No channels in response results")
                return None
                
            result = response["results"]["channels"][0]["alternatives"][0]
            
            # Log detected language if available
            if "detected_language" in result:
                detected_lang = result["detected_language"]
                logger.info(f"Detected language: {detected_lang}")
            
            # Process transcript based on available features
            formatted_transcript = await self._process_enhanced_transcript(response["results"], settings)

            if not formatted_transcript.strip():
                logger.warning("Empty transcript received from Deepgram")
                return None

            logger.info(f"Successfully transcribed audio file: {len(formatted_transcript)} characters")
            return formatted_transcript

        except asyncio.TimeoutError:
            logger.error(f"Transcription timed out after {self.timeout_seconds} seconds")
            return None
        except Exception as e:
            logger.error(f"Error transcribing audio: {e}", exc_info=True)
            return None

    async def _process_enhanced_transcript(self, results: dict, settings) -> str:
        """
        Process transcript with enhanced formatting using paragraphs and speaker information.
        
        Args:
            results: Deepgram results dictionary
            settings: Application settings
            
        Returns:
            Enhanced formatted transcript
        """
        try:
            alternative = results["channels"][0]["alternatives"][0]
            
            # Debug logging to understand the response structure
            logger.info(f"Available keys in alternative: {list(alternative.keys())}")
            logger.info(f"Available keys in results: {list(results.keys())}")
            
            # Check if we have paragraphs (preferred method)
            if "paragraphs" in alternative:
                paragraphs_data = alternative["paragraphs"]
                logger.info(f"Found paragraphs key. Type: {type(paragraphs_data)}")
                if isinstance(paragraphs_data, dict):
                    logger.info(f"Paragraphs dict keys: {list(paragraphs_data.keys())}")
                    if "paragraphs" in paragraphs_data and paragraphs_data["paragraphs"]:
                        logger.info(f"Processing {len(paragraphs_data['paragraphs'])} paragraphs with enhanced formatting")
                        return self._format_transcript_with_paragraphs(paragraphs_data["paragraphs"], settings)
                elif isinstance(paragraphs_data, list) and len(paragraphs_data) > 0:
                    logger.info(f"Processing {len(paragraphs_data)} paragraphs (direct list) with enhanced formatting")
                    return self._format_transcript_with_paragraphs(paragraphs_data, settings)
            
            # Fallback: Check for utterances if paragraphs not available
            if ("utterances" in results and 
                results["utterances"] and 
                len(results["utterances"]) > 0):
                
                logger.info(f"Fallback: Processing {len(results['utterances'])} utterances")
                return self._format_transcript_with_speakers(results["utterances"])
            
            # Final fallback: Basic transcript
            basic_transcript = alternative.get("transcript", "")
            logger.info(f"Using basic transcript (no paragraphs or speaker info available). Length: {len(basic_transcript)}")
            if not basic_transcript:
                logger.warning("Basic transcript is also empty!")
                # Let's log more details to debug
                logger.debug(f"Alternative structure: {alternative}")
            return basic_transcript
                
        except Exception as e:
            logger.error(f"Error processing enhanced transcript: {e}", exc_info=True)
            # Return basic transcript as ultimate fallback
            try:
                fallback = results["channels"][0]["alternatives"][0].get("transcript", "")
                logger.info(f"Exception fallback transcript length: {len(fallback)}")
                return fallback
            except Exception as fallback_error:
                logger.error(f"Even fallback failed: {fallback_error}")
                return ""

    def _format_transcript_with_paragraphs(self, paragraphs: list, settings) -> str:
        """
        Format transcript using paragraphs with speaker information for better readability.
        
        Args:
            paragraphs: List of paragraph objects from Deepgram
            settings: Application settings
            
        Returns:
            Well-formatted transcript with paragraphs and speaker labels
        """
        formatted_sections = []
        
        for paragraph in paragraphs:
            sentences = paragraph.get("sentences", [])
            speaker = paragraph.get("speaker", 0)  # Speaker is at paragraph level
            
            if not sentences:
                continue
            
            # Combine all sentences in the paragraph
            paragraph_text = " ".join([sentence.get("text", "").strip() for sentence in sentences if sentence.get("text", "").strip()])
            
            if paragraph_text:
                if settings.enable_diarization and speaker is not None:
                    formatted_sections.append(f"Speaker {speaker}: {paragraph_text}")
                else:
                    formatted_sections.append(paragraph_text)
        
        # Join sections with double line breaks for better paragraph separation
        return "\n\n".join(formatted_sections)

    def _format_transcript_with_speakers(self, utterances: list) -> str:
        """
        Format transcript with speaker labels (fallback method).
        
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