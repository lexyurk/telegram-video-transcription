"""Abstract AI model interface for different ML providers."""

from abc import ABC, abstractmethod
from typing import Dict, Optional

from anthropic import AsyncAnthropic
from google import genai
from loguru import logger

from telegram_bot.config import get_settings


class AIModel(ABC):
    """Abstract base class for AI models."""

    @abstractmethod
    async def generate_text(self, prompt: str) -> str | None:
        """Generate text response from the AI model."""
        pass


class GeminiModel(AIModel):
    """Google Gemini AI model implementation."""

    def __init__(self, api_key: str, model_name: str = "gemini-3-pro-preview") -> None:
        """Initialize Gemini model."""
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        logger.info(f"Initialized Gemini model: {model_name}")

    async def generate_text(self, prompt: str) -> str | None:
        """Generate text using Gemini."""
        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt]
            )
            return response.text
        except Exception as e:
            logger.error(f"Error generating text with Gemini: {e}")
            return None


class ClaudeModel(AIModel):
    """Anthropic Claude AI model implementation."""

    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-5-20250929") -> None:
        """Initialize Claude model."""
        self.client = AsyncAnthropic(api_key=api_key)
        self.model_name = model_name
        logger.info(f"Initialized Claude model: {model_name}")

    async def generate_text(self, prompt: str, max_tokens: int = 8000) -> str | None:
        """Generate text using Claude."""
        try:
            message = await self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error generating text with Claude: {e}")
            return None


def create_ai_model() -> AIModel:
    """
    Create an AI model instance based on available API keys.
    
    Priority: Gemini > Claude
    
    Returns:
        AIModel instance
        
    Raises:
        ValueError: If no valid API keys are provided
    """
    settings = get_settings()
    
    # Check for Gemini API key first (priority)
    if settings.google_api_key:
        logger.info("Using Gemini model (Google API key provided)")
        return GeminiModel(
            api_key=settings.google_api_key,
            model_name=settings.gemini_model
        )
    
    # Fallback to Claude
    elif settings.anthropic_api_key:
        logger.info("Using Claude model (Anthropic API key provided)")
        return ClaudeModel(
            api_key=settings.anthropic_api_key,
            model_name=settings.claude_model
        )
    
    else:
        raise ValueError(
            "No AI model API key provided. Please set either GOOGLE_API_KEY or ANTHROPIC_API_KEY"
        ) 