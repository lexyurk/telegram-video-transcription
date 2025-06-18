"""Summarization service for handling Claude AI summarization."""

from anthropic import AsyncAnthropic
from loguru import logger

from telegram_bot.config import get_settings


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
Please analyze the following transcript and provide a comprehensive summary. 

IMPORTANT: Respond in the same language as the input transcript. If the transcript is in Spanish, respond in Spanish. If it's in English, respond in English, etc.

Please provide:

1. **Executive Summary**: A brief overview of the main topics discussed
2. **Key Points**: The most important information and insights
3. **Action Items**: Specific actions mentioned or implied that need to be taken
4. **Next Steps**: Recommended follow-up actions

Please format your response clearly with headers and bullet points for easy reading. Use the same language as the transcript for all sections including headers.

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