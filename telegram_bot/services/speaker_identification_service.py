"""Speaker identification service for detecting and replacing speaker names."""

import json
import re
from typing import Dict, Optional, Set
from collections import Counter

from loguru import logger

from telegram_bot.services.ai_model import AIModel, create_ai_model


class SpeakerIdentificationService:
    """Service for identifying speaker names from transcripts using AI."""

    def __init__(self, ai_model: AIModel | None = None) -> None:
        """Initialize the speaker identification service."""
        self.ai_model = ai_model or create_ai_model()

    def _disambiguate_speaker_names(self, speaker_names: Dict[str, str]) -> Dict[str, str]:
        """
        Disambiguate speaker names by adding suffixes when multiple speakers have the same name.
        
        Args:
            speaker_names: Original mapping of speaker IDs to names
            
        Returns:
            Updated mapping with disambiguated names
        """
        if not speaker_names:
            return speaker_names
            
        # Count occurrences of each name
        name_counts = Counter(speaker_names.values())
        
        # Find names that appear more than once
        duplicate_names = {name for name, count in name_counts.items() if count > 1}
        
        if not duplicate_names:
            # No duplicates, return original
            return speaker_names
            
        logger.info(f"Found duplicate names that need disambiguation: {duplicate_names}")
        
        # Create disambiguated names
        disambiguated_names = {}
        name_counters = {}
        
        for speaker_id, name in speaker_names.items():
            if name in duplicate_names:
                # This name appears multiple times, add a suffix
                if name not in name_counters:
                    name_counters[name] = 1
                else:
                    name_counters[name] += 1
                
                if name_counters[name] == 1:
                    # First occurrence gets " (1)" suffix
                    disambiguated_name = f"{name} (1)"
                else:
                    # Subsequent occurrences get increasing numbers
                    disambiguated_name = f"{name} ({name_counters[name]})"
                
                disambiguated_names[speaker_id] = disambiguated_name
                logger.info(f"Speaker {speaker_id}: '{name}' -> '{disambiguated_name}'")
            else:
                # Name is unique, keep as is
                disambiguated_names[speaker_id] = name
                
        return disambiguated_names

    async def identify_speakers(self, transcript: str) -> Dict[str, str] | None:
        """
        Identify speaker names from the transcript using AI.

        Args:
            transcript: The transcript with speaker labels (Speaker 0, Speaker 1, etc.)

        Returns:
            Dictionary mapping speaker numbers to names (e.g., {"0": "Alexander", "1": "Alexey"})
            or None if identification failed. Names are automatically disambiguated if duplicates exist.
        """
        try:
            # Check if transcript has speaker labels
            if "Speaker " not in transcript and "Спикер " not in transcript:
                logger.info("No speaker labels found in transcript")
                return {}

            explicit_names = self._extract_explicit_self_introductions(transcript)

            prompt = f"""
Please analyze the following transcript and identify the names of the speakers.

The transcript uses labels like "Speaker 0:", "Speaker 1:", etc. Your task is to:
1. Listen carefully to how speakers address each other or introduce themselves
2. Identify explicit self-introductions (e.g., variants of "for artificial intelligence, my name is <X>", "для ИИ меня зовут <X>", "for the record, I'm <X>") and map them to the correct "Speaker N" who said it
3. Identify the actual names of each speaker
4. Return ONLY a JSON object mapping speaker numbers to names

Rules:
- Only include speakers whose names you can confidently identify from the conversation
- Use the exact speaker numbers from the transcript (0, 1, 2, etc.)
- If a name is mentioned but you're not sure which speaker it belongs to, don't include it
- If no names can be identified, return an empty JSON object: {{}}
- Return ONLY the JSON object, no other text or explanation
- If multiple speakers have the same name, still map them to the same name - the system will handle disambiguation automatically

Known explicit self-introductions (use these as authoritative hints when present):
{json.dumps(explicit_names, ensure_ascii=False)}

 Example output format:
{{
  "0": "Alexander",
  "1": "Alexey",
  "2": "Maria"
}}

Transcript:
{transcript}
"""

            response_text = await self.ai_model.generate_text(prompt)
            if not response_text:
                logger.warning("No response from AI model")
                return {}
            
            response_text = response_text.strip()
            
            # Try to extract JSON from the response
            try:
                # Look for JSON object in the response
                json_match = re.search(r'\{[^}]*\}', response_text)
                if json_match:
                    json_str = json_match.group()
                    speaker_names = json.loads(json_str)
                    
                    # Validate the format
                    if isinstance(speaker_names, dict):
                        # Ensure all keys are strings and values are strings
                        validated_names = {}
                        for speaker_id, name in speaker_names.items():
                            if isinstance(speaker_id, (str, int)) and isinstance(name, str):
                                validated_names[str(speaker_id)] = name.strip()
                        
                        # Merge AI-detected names with explicit introductions (explicit wins on conflict)
                        merged = dict(validated_names)
                        try:
                            if 'explicit_names' in locals() and explicit_names:
                                merged.update({k: v for k, v in explicit_names.items() if v})
                        except Exception:
                            pass
                        
                        # Disambiguate names if there are duplicates
                        disambiguated_names = self._disambiguate_speaker_names(merged)
                        
                        logger.info(f"Successfully identified {len(disambiguated_names)} speakers: {disambiguated_names}")
                        return disambiguated_names
                    
                else:
                    logger.warning("No JSON object found in AI response")
                    return {}
                    
            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from AI response: {e}")
                logger.debug(f"AI response was: {response_text}")
                return {}

        except Exception as e:
            logger.error(f"Error identifying speakers: {e}")
            return None

    def _extract_explicit_self_introductions(self, transcript: str) -> Dict[str, str]:
        """
        Extract names from explicit self-introduction phrases tied to specific speakers.

        Supports phrases like:
        - "for artificial intelligence, my name is <Name>"
        - "for the record, my name is <Name>"
        - "для ИИ меня зовут <Имя>" / "для искусственного интеллекта меня зовут <Имя>"

        Returns a mapping of speaker number to detected name.
        """
        names: Dict[str, str] = {}
        line_pattern = re.compile(r"^(?:Speaker|Спикер)\s*(\d+)\s*:\s*(.*)$", re.IGNORECASE)
        patterns = [
            re.compile(r"(?:for\s+(?:artificial\s+intelligence|ai)|for\s+the\s+record)[^\w]{0,10}.*?my\s+name\s+is\s+([A-Za-zА-Яа-яЁё\-\s]{2,60})", re.IGNORECASE),
            re.compile(r"для\s+(?:искусственного\s+интеллекта|ии)[^\w]{0,10}.*?меня\s+зовут\s+([A-Za-zА-Яа-яЁё\-\s]{2,60})", re.IGNORECASE),
        ]
        for raw_line in transcript.split('\n'):
            line = raw_line.strip()
            m = line_pattern.match(line)
            if not m:
                continue
            speaker_id, content = m.group(1), m.group(2)
            for pat in patterns:
                nm = pat.search(content)
                if nm:
                    name = nm.group(1).strip().strip('\"'"'"'«».,!?:;')
                    name = re.sub(r"\s+", " ", name)
                    if name:
                        names[str(speaker_id)] = name
                        break
        if names:
            logger.info(f"Explicit self-introductions detected: {names}")
        return names

    def replace_speaker_labels(self, transcript: str, speaker_names: Dict[str, str]) -> str:
        """
        Replace generic speaker labels with actual names in the transcript.

        Args:
            transcript: The original transcript with Speaker 0, Speaker 1, etc.
            speaker_names: Dictionary mapping speaker numbers to names (may include disambiguated names)

        Returns:
            Updated transcript with actual speaker names
        """
        if not speaker_names:
            return transcript

        updated_transcript = transcript
        
        # Replace each speaker label with the actual name
        for speaker_id, name in speaker_names.items():
            # Replace English and Russian diarization labels
            replacement = f"{name}:"
            updated_transcript = updated_transcript.replace(f"Speaker {speaker_id}:", replacement)
            updated_transcript = updated_transcript.replace(f"Спикер {speaker_id}:", replacement)
            
            logger.info(f"Replaced 'Speaker {speaker_id}:' with '{name}:'")

        return updated_transcript

    async def process_transcript_with_speaker_names(self, transcript: str) -> str:
        """
        Complete pipeline: identify speakers and replace labels in transcript.
        Automatically handles name disambiguation for speakers with the same name.

        Args:
            transcript: The original transcript with generic speaker labels

        Returns:
            Updated transcript with actual speaker names (or original if identification failed)
        """
        try:
            # First, identify the speakers
            speaker_names = await self.identify_speakers(transcript)
            
            if speaker_names is None:
                logger.error("Failed to identify speakers, returning original transcript")
                return transcript
            
            if not speaker_names:
                logger.info("No speakers identified, returning original transcript")
                return transcript
            
            # Replace the labels with actual names (already disambiguated)
            updated_transcript = self.replace_speaker_labels(transcript, speaker_names)
            
            logger.info(f"Successfully processed transcript with {len(speaker_names)} identified speakers")
            return updated_transcript
            
        except Exception as e:
            logger.error(f"Error processing transcript with speaker names: {e}")
            return transcript 