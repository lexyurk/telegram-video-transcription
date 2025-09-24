"""Abstract AI model interface for different ML providers."""

import json
from abc import ABC, abstractmethod
from typing import Any, Dict, Optional

from anthropic import AsyncAnthropic
from google import genai
from loguru import logger

from telegram_bot.config import get_settings, Settings


class AIModel(ABC):
    """Abstract base class for AI models."""

    @abstractmethod
    async def generate_text(self, prompt: str) -> str | None:
        """Generate text response from the AI model."""
        pass

    async def generate_json(
        self,
        prompt: str,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fallback JSON generation via plain text response."""

        text = await self.generate_text(prompt)
        if not text:
            return {}
        cleaned = text.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(line for line in cleaned.splitlines() if not line.startswith("```"))
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            logger.warning("Failed to parse JSON response from model")
            return {}


class GeminiModel(AIModel):
    """Google Gemini AI model implementation."""

    def __init__(self, api_key: str, model_name: str = "gemini-2.5-flash") -> None:
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

    async def generate_json(
        self,
        prompt: str,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            kwargs: Dict[str, Any] = {}
            if response_schema:
                kwargs["response_schema"] = response_schema
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                response_mime_type="application/json",
                **kwargs,
            )
            payload = response.text
            if not payload and response.candidates:
                parts = response.candidates[0].content.parts
                if parts:
                    payload = parts[0].text
            if not payload:
                return {}
            return json.loads(payload)
        except Exception as e:
            logger.error(f"Error generating structured JSON with Gemini: {e}")
            return {}


class ClaudeModel(AIModel):
    """Anthropic Claude AI model implementation."""

    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-20250514") -> None:
        """Initialize Claude model."""
        self.client = AsyncAnthropic(api_key=api_key)
        self.model_name = model_name
        logger.info(f"Initialized Claude model: {model_name}")

    async def generate_text(self, prompt: str) -> str | None:
        """Generate text using Claude."""
        try:
            message = await self.client.messages.create(
                model=self.model_name,
                max_tokens=4000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as e:
            logger.error(f"Error generating text with Claude: {e}")
            return None

    async def generate_json(
        self,
        prompt: str,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            kwargs: Dict[str, Any] = {}
            if response_schema:
                kwargs["response_format"] = {"type": "json_object", "schema": response_schema}
            else:
                kwargs["response_format"] = {"type": "json_object"}
            message = await self.client.messages.create(
                model=self.model_name,
                max_tokens=4000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
                **kwargs,
            )
            if not message.content:
                return {}
            payload = message.content[0].text
            if not payload:
                return {}
            return json.loads(payload)
        except Exception as e:
            logger.error(f"Error generating structured JSON with Claude: {e}")
            return {}


def create_ai_model(settings: Optional[Settings] = None) -> AIModel:
    """
    Create an AI model instance based on available API keys.
    
    Priority: Gemini > Claude
    
    Returns:
        AIModel instance
        
    Raises:
        ValueError: If no valid API keys are provided
    """
    settings = settings or get_settings()

    google_key = settings.google_api_key
    anthropic_key = settings.anthropic_api_key

    gemini_model_name = settings.gemini_model
    claude_model_name = settings.claude_model

    # Check for Gemini API key first (priority)
    if google_key:
        logger.info("Using Gemini model (Google API key provided)")
        return GeminiModel(
            api_key=google_key,
            model_name=gemini_model_name,
        )

    # Fallback to Claude
    if anthropic_key:
        logger.info("Using Claude model (Anthropic API key provided)")
        return ClaudeModel(
            api_key=anthropic_key,
            model_name=claude_model_name,
        )

    raise ValueError(
        "No AI model API key provided. Please set either GOOGLE_API_KEY or ANTHROPIC_API_KEY"
    ) 