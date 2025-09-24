"""Abstract AI model interface for different ML providers."""

from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Dict, Optional

from anthropic import AsyncAnthropic
import google.generativeai as genai
from loguru import logger

from telegram_bot.config import get_settings, Settings


@dataclass
class GenerationResult:
    """Container for text generation responses and billing metadata."""

    text: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    provider: str
    model: str


class AIModel(ABC):
    """Abstract base class for AI models."""

    @abstractmethod
    async def generate_text_with_metadata(self, prompt: str) -> GenerationResult | None:
        """Generate text plus token usage metadata."""
        raise NotImplementedError

    async def generate_text(self, prompt: str) -> str | None:
        result = await self.generate_text_with_metadata(prompt)
        return result.text if result else None

    async def generate_json(
        self,
        prompt: str,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fallback JSON generation by parsing plain text output."""

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
        genai.configure(api_key=api_key)
        self.model_name = model_name
        self.model = genai.GenerativeModel(model_name=self.model_name)
        logger.info(f"Initialized Gemini model: {model_name}")

    async def generate_text_with_metadata(self, prompt: str) -> GenerationResult | None:
        try:
            response = self.model.generate_content(prompt)
            text = response.text or ""
            usage = getattr(response, "usage_metadata", None)
            prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
            completion_tokens = getattr(usage, "candidates_token_count", 0) or 0
            total_tokens = getattr(usage, "total_token_count", prompt_tokens + completion_tokens) or (
                prompt_tokens + completion_tokens
            )
            return GenerationResult(
                text=text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                provider="gemini",
                model=self.model_name,
            )
        except Exception as e:
            logger.error(f"Error generating text with Gemini: {e}")
            return None

    async def generate_json(
        self,
        prompt: str,
        response_schema: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        try:
            generation_config: Dict[str, Any] = {}
            if response_schema:
                generation_config["response_mime_type"] = "application/json"
                generation_config["response_schema"] = response_schema
            response = self.model.generate_content(
                prompt,
                generation_config=generation_config or None,
            )
            payload = response.text
            if not payload:
                return {}
            return json.loads(payload)
        except Exception as e:
            logger.error(f"Error generating structured JSON with Gemini: {e}")
            return await super().generate_json(prompt, response_schema)


class ClaudeModel(AIModel):
    """Anthropic Claude AI model implementation."""

    def __init__(self, api_key: str, model_name: str = "claude-sonnet-4-20250514") -> None:
        """Initialize Claude model."""
        self.client = AsyncAnthropic(api_key=api_key)
        self.model_name = model_name
        logger.info(f"Initialized Claude model: {model_name}")

    async def generate_text_with_metadata(self, prompt: str) -> GenerationResult | None:
        try:
            message = await self.client.messages.create(
                model=self.model_name,
                max_tokens=4000,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            text = message.content[0].text if message.content else ""
            usage = getattr(message, "usage", None)
            prompt_tokens = getattr(usage, "input_tokens", 0) or 0
            completion_tokens = getattr(usage, "output_tokens", 0) or 0
            total_tokens = prompt_tokens + completion_tokens
            return GenerationResult(
                text=text,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
                provider="claude",
                model=self.model_name,
            )
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
            return await super().generate_json(prompt, response_schema)


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