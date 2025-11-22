"""Transcription service for handling Deepgram transcription."""

import asyncio
import aiofiles
from deepgram import DeepgramClient
import httpx
from loguru import logger

from telegram_bot.config import get_settings


class TranscriptionService:
    """Service for handling Deepgram transcription with advanced features."""

    def __init__(self) -> None:
        """Initialize the transcription service."""
        settings = get_settings()
        
        # Initialize Deepgram client with default configuration
        # We'll pass timeout directly to transcribe_file method
        self.client = DeepgramClient(settings.deepgram_api_key)
        self.timeout_seconds = settings.deepgram_timeout_seconds
        
        logger.info(f"Initialized Deepgram client with {self.timeout_seconds}s timeout")

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
            options = self._build_prerecorded_options(settings)

            async with aiofiles.open(file_path, "rb") as audio_file:
                buffer_data = await audio_file.read()

            payload = {"buffer": buffer_data}
            
            file_size_mb = len(buffer_data) / (1024 * 1024)
            dynamic_timeout = max(300, int(file_size_mb * 120) + 300)
            actual_timeout = min(dynamic_timeout, self.timeout_seconds)

            logger.info(f"Starting enhanced transcription for file: {file_path} ({len(buffer_data)} bytes)")
            logger.info(f"Features enabled: diarization={settings.enable_diarization}, punctuation={settings.enable_punctuation}, smart_format={settings.enable_smart_format}, paragraphs={settings.enable_paragraphs}")
            logger.info(f"File size: {file_size_mb:.1f}MB, Dynamic timeout: {actual_timeout}s (calculated: {dynamic_timeout}s, max: {self.timeout_seconds}s)")

            try:
                timeout_config = httpx.Timeout(
                    connect=60.0,
                    read=actual_timeout,
                    write=600.0,
                    pool=10.0
                )
                
                logger.info(f"Using timeout: connect=60s, read={actual_timeout}s, write=600s, pool=10s")
                
                response = await asyncio.to_thread(
                    self.client.listen.prerecorded.v("1").transcribe_file,
                    payload,
                    options,
                    timeout=timeout_config
                )
            except Exception as e:
                error_msg = str(e).lower()
                if "write operation timed out" in error_msg or "timeout" in error_msg:
                    logger.error(f"HTTP timeout during file upload: {e}")
                    logger.error("This suggests network issues or the file upload took too long")
                    logger.error("Consider checking network connectivity or file size")
                else:
                    logger.error(f"Deepgram API call failed: {e}")
                raise

            logger.info("Received response from Deepgram, processing...")
            
            if hasattr(response, 'to_dict'):
                response = response.to_dict()
            elif hasattr(response, '__dict__'):
                response = response.__dict__

            if "results" not in response:
                logger.error(f"No 'results' key in response. Available keys: {list(response.keys()) if hasattr(response, 'keys') else 'No keys'}")
                return None
                
            if not response["results"]["channels"]:
                logger.error("No channels in response results")
                return None
                
            result = response["results"]["channels"][0]["alternatives"][0]
            
            if "detected_language" in result:
                detected_lang = result["detected_language"]
                logger.info(f"Detected language: {detected_lang}")
            else:
                logger.warning("No language detected in response")
            
            confidence = result.get("confidence", 0)
            logger.info(f"Transcription confidence: {confidence}")
            
            logger.debug(f"Raw alternative keys: {list(result.keys())}")
            logger.debug(f"Raw result confidence: {result.get('confidence', 'N/A')}")
            logger.debug(f"Raw basic transcript (first 100 chars): '{result.get('transcript', '')[:100]}'")
            
            formatted_transcript = await self._process_enhanced_transcript(response["results"], settings)

            if not formatted_transcript.strip():
                logger.warning("Empty transcript received from Deepgram")
                return None

            logger.info(f"Successfully transcribed audio file: {len(formatted_transcript)} characters")
            return formatted_transcript

        except asyncio.TimeoutError:
            logger.error(f"Transcription timed out after {actual_timeout} seconds")
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
            
            logger.info(f"Available keys in alternative: {list(alternative.keys())}")
            logger.info(f"Available keys in results: {list(results.keys())}")
            if "paragraphs" in alternative:
                paragraphs_data = alternative["paragraphs"]
                logger.info(f"Found paragraphs key. Type: {type(paragraphs_data)}")
                if isinstance(paragraphs_data, dict):
                    logger.info(f"Paragraphs dict keys: {list(paragraphs_data.keys())}")
                    if "paragraphs" in paragraphs_data:
                        actual_paragraphs = paragraphs_data["paragraphs"]
                        logger.info(f"Paragraphs list type: {type(actual_paragraphs)}, length: {len(actual_paragraphs) if actual_paragraphs else 'None/Empty'}")
                        if actual_paragraphs and len(actual_paragraphs) > 0:
                            logger.info(f"Processing {len(actual_paragraphs)} paragraphs with enhanced formatting")
                            return self._format_transcript_with_paragraphs(actual_paragraphs, settings)
                        else:
                            logger.warning(f"Paragraphs list is empty or None: {actual_paragraphs}")
                    
                    if "transcript" in paragraphs_data:
                        paragraphs_transcript = paragraphs_data["transcript"]
                        logger.info(f"Found paragraphs transcript. Length: {len(paragraphs_transcript) if paragraphs_transcript else 0}")
                        logger.debug(f"Paragraphs transcript content (first 200 chars): '{paragraphs_transcript[:200] if paragraphs_transcript else 'None'}'")
                        if paragraphs_transcript and paragraphs_transcript.strip():
                            logger.info("Using pre-formatted paragraphs transcript")
                            return paragraphs_transcript.strip()
                        else:
                            logger.warning(f"Paragraphs transcript is empty after strip. Raw: '{paragraphs_transcript}'")
                    else:
                        logger.warning("No 'transcript' key in paragraphs_data")
                elif isinstance(paragraphs_data, list) and len(paragraphs_data) > 0:
                    logger.info(f"Processing {len(paragraphs_data)} paragraphs (direct list) with enhanced formatting")
                    return self._format_transcript_with_paragraphs(paragraphs_data, settings)
                else:
                    logger.warning(f"Unexpected paragraphs_data type: {type(paragraphs_data)}, value: {paragraphs_data}")
            else:
                logger.warning("No 'paragraphs' key found in alternative")
            

            if ("utterances" in results and 
                results["utterances"] and 
                len(results["utterances"]) > 0):
                
                logger.info(f"Fallback: Processing {len(results['utterances'])} utterances")
                return self._format_transcript_with_speakers(results["utterances"])
            else:
                logger.warning(f"No utterances available. Utterances in results: {'utterances' in results}, utterances value: {results.get('utterances', 'Missing')}")
            

            basic_transcript = alternative.get("transcript", "")
            logger.info(f"Using basic transcript (no paragraphs or speaker info available). Length: {len(basic_transcript)}")
            if not basic_transcript:
                logger.warning("Basic transcript is also empty!")
                # Let's log more details to debug
                logger.debug(f"Alternative structure: {alternative}")
                logger.debug(f"Full results structure keys: {list(results.keys())}")
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
            speaker = paragraph.get("speaker", 0)
            
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

    def _extract_segments_from_results(self, results: dict) -> list[dict]:
        """
        Extract diarized segments with timestamps from Deepgram results.
        Returns a list of dicts: {start: float, end: float, speaker: int, text: str}
        """
        segments: list[dict] = []
        try:
            alt = results["channels"][0]["alternatives"][0]
            paragraphs_data = alt.get("paragraphs")
            paragraphs = None
            if isinstance(paragraphs_data, dict):
                paragraphs = paragraphs_data.get("paragraphs")
            elif isinstance(paragraphs_data, list):
                paragraphs = paragraphs_data
            if paragraphs:
                for paragraph in paragraphs:
                    speaker = paragraph.get("speaker")
                    for sentence in paragraph.get("sentences", []) or []:
                        start = sentence.get("start") or sentence.get("start_time")
                        end = sentence.get("end") or sentence.get("end_time")
                        text = sentence.get("text", "")
                        if start is not None and end is not None and speaker is not None:
                            try:
                                segments.append({
                                    "start": float(start),
                                    "end": float(end),
                                    "speaker": int(speaker),
                                    "text": text,
                                })
                            except Exception:
                                pass
            if not segments:
                for utt in results.get("utterances", []) or []:
                    start = utt.get("start")
                    end = utt.get("end")
                    speaker = utt.get("speaker")
                    text = utt.get("transcript", "")
                    if start is not None and end is not None and speaker is not None:
                        try:
                            segments.append({
                                "start": float(start),
                                "end": float(end),
                                "speaker": int(speaker),
                                "text": text,
                            })
                        except Exception:
                            pass
            # Fallback: build segments from words if still empty
            if not segments:
                words = alt.get("words") or []
                # Group consecutive words by speaker with short gaps
                current = None
                last_end = None
                for w in words:
                    s = w.get("speaker")
                    start = w.get("start")
                    end = w.get("end")
                    text = w.get("word") or w.get("punctuated_word") or ""
                    if s is None or start is None or end is None:
                        continue
                    s = int(s)
                    start = float(start)
                    end = float(end)
                    if current and current["speaker"] == s and last_end is not None and start - last_end <= 0.5:
                        # continue segment
                        current["end"] = end
                        if text:
                            current["text"] += (" " if current["text"] else "") + text
                    else:
                        # flush previous
                        if current:
                            segments.append(current)
                        current = {"start": start, "end": end, "speaker": s, "text": text}
                    last_end = end
                if current:
                    segments.append(current)
        except Exception as e:
            logger.warning(f"Failed to extract segments: {e}")
        return segments

    async def transcribe_with_segments(self, file_path: str) -> tuple[str | None, list[dict]]:
        """
        Transcribe audio and also return diarized segments with timestamps for alignment.
        Returns (formatted_transcript or None, segments list).
        """
        try:
            settings = get_settings()
            options = self._build_prerecorded_options(settings)
            async with aiofiles.open(file_path, "rb") as audio_file:
                buffer_data = await audio_file.read()
            payload = {"buffer": buffer_data}
            file_size_mb = len(buffer_data) / (1024 * 1024)
            dynamic_timeout = max(300, int(file_size_mb * 120) + 300)
            actual_timeout = min(dynamic_timeout, self.timeout_seconds)
            timeout_config = httpx.Timeout(connect=60.0, read=actual_timeout, write=600.0, pool=10.0)
            response = await asyncio.to_thread(
                self.client.listen.prerecorded.v("1").transcribe_file,
                payload,
                options,
                timeout=timeout_config,
            )
            if hasattr(response, 'to_dict'):
                response = response.to_dict()
            elif hasattr(response, '__dict__'):
                response = response.__dict__
            if "results" not in response or not response["results"].get("channels"):
                return None, []
            results = response["results"]
            segments = self._extract_segments_from_results(results)
            formatted_transcript = await self._process_enhanced_transcript(results, settings)
            if not formatted_transcript or not formatted_transcript.strip():
                formatted_transcript = None
            return formatted_transcript, segments
        except Exception as e:
            logger.error(f"Error in transcribe_with_segments: {e}", exc_info=True)
            return None, []

    def _build_prerecorded_options(self, settings) -> dict:
        """Construct a Deepgram prerecorded options payload compatible across SDK versions."""
        return {
            "model": settings.deepgram_model,
            "detect_language": True,
            "smart_format": settings.enable_smart_format,
            "punctuate": settings.enable_punctuation,
            "paragraphs": settings.enable_paragraphs,
            "diarize": settings.enable_diarization,
            "filler_words": settings.enable_filler_words,
            "profanity_filter": settings.enable_profanity_filter,
        }