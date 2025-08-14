"""Summarization service for handling AI summarization."""

import re
from loguru import logger

from telegram_bot.services.ai_model import AIModel


class SummarizationService:
    """Service for creating summaries with action points using AI models."""

    def __init__(self, ai_model: AIModel | None = None) -> None:
        """Initialize the summarization service."""
        from telegram_bot.services.ai_model import create_ai_model
        
        self.ai_model = ai_model or create_ai_model()

    def _remove_speaker_labels(self, text: str) -> str:
        """
        Remove speaker labels from transcript to avoid language confusion in AI.
        
        Args:
            text: Transcript with speaker labels
            
        Returns:
            Clean transcript without speaker labels
        """
        import re
        
        # Only remove generic diarization labels like "Speaker 0:" or "Спикер 1:"
        # Preserve real name labels (e.g., "Alexey:") so ownership can be inferred.
        lines = text.split('\n')
        cleaned_lines = []

        for line in lines:
            # Remove only generic speaker labels
            cleaned_line = re.sub(r'^(?:Speaker|Спикер)\s*\d+\s*:\s*', '', line.strip())
            if cleaned_line:  # Only add non-empty lines
                cleaned_lines.append(cleaned_line)

        return ' '.join(cleaned_lines)

    def _sanitize_markdown(self, text: str) -> str:
        """
        Sanitize markdown text to prevent Telegram parsing errors.
        
        Args:
            text: Raw markdown text
            
        Returns:
            Sanitized markdown text
        """
        # Remove or fix common problematic markdown patterns
        
        # Fix unmatched bold markers
        text = re.sub(r'\*\*([^*]*)\*(?!\*)', r'**\1**', text)  # Fix single * after **
        text = re.sub(r'(?<!\*)\*([^*]*)\*\*', r'**\1**', text)  # Fix single * before **
        
        # Fix unmatched italic markers
        text = re.sub(r'(?<!\*)\*([^*\n]+)(?!\*)', r'_\1_', text)  # Convert single * to _
        
        # Fix unmatched code blocks
        text = re.sub(r'```([^`]*)$', r'```\1```', text, flags=re.MULTILINE)  # Close unclosed code blocks
        
        # Fix unmatched inline code
        text = re.sub(r'`([^`\n]*?)(?=\n|$)', r'`\1`', text)  # Close unclosed inline code
        
        # Remove any remaining problematic characters that could break parsing
        text = re.sub(r'[^\w\s\n\r\*_`#\-\.\!\?\(\)\[\]:\|]', '', text)
        
        return text.strip()

    async def create_summary_with_action_points(self, transcript: str) -> str | None:
        """
        Create a summary with action points using AI.

        Args:
            transcript: The transcript text to summarize

        Returns:
            Summary with action points or None if failed
        """
        try:
            if not transcript.strip():
                logger.warning("Empty transcript provided for summarization")
                return None

            # Remove speaker labels to avoid language confusion in AI
            clean_transcript = self._remove_speaker_labels(transcript)
            logger.info(f"Removed speaker labels for summarization. Original: {len(transcript)} chars, Clean: {len(clean_transcript)} chars")

            # Improved prompt for cleaner markdown output and explicit AI task capture
            prompt = f"""Analyze this meeting transcript and create a focused summary with actionable insights.

LANGUAGE: Respond in the same language as the transcript.

FORMATTING: Use simple markdown - **bold** for headers, - for bullet points. Keep markdown balanced.

Structure your response as:

**Executive Summary**
- 1-3 sentences summarizing outcomes and significance

**Key Points**
- What decisions were made and why
- Important insights or discoveries
- Problems identified and solutions proposed

**Action Items**
- [Person/Role] will [specific action] by [timeframe if mentioned]
- Include who is responsible for each action
- Prioritize urgent items first

**Tasks for AI (if any)**
- Detect phrases that explicitly assign a "task for AI" (e.g., "task for artificial intelligence", "задача для ИИ").
- Extract the task as a concrete, actionable item.
- Assign to the speaker who said it unless a specific assignee is named; if named, use that person.

**Next Steps**
- Immediate follow-ups needed
- Dependencies or blockers mentioned
- Future discussions or meetings planned

Focus on:
- WHY decisions were made, not just what was discussed
- Concrete next steps with clear ownership
- Key insights that drive the actions
- Skip routine updates unless they impact decisions

Transcript (cleaned):
{clean_transcript}

Original transcript (with labels) for reference:
{transcript}"""

            summary = await self.ai_model.generate_text(prompt)
            
            if summary:
                # Sanitize the markdown before returning
                sanitized_summary = self._sanitize_markdown(summary)
                logger.info(f"Successfully created summary: {len(sanitized_summary)} characters")
                return sanitized_summary
            else:
                logger.error("AI model returned empty summary")
                return None

        except Exception as e:
            logger.error(f"Error creating summary: {e}", exc_info=True)
            return None 