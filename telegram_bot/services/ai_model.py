"""Shared text generation interface for the supported AI providers."""

import asyncio
from abc import ABC, abstractmethod

import httpx
from anthropic import AsyncAnthropic
from google import genai
from loguru import logger

from telegram_bot.config import get_settings


class AIModel(ABC):
    """Abstract base class for AI models."""

    @abstractmethod
    async def generate_text(self, prompt: str, max_tokens: int = 8000) -> str | None:
        """Generate text, returning None when the provider fails."""


class GeminiModel(AIModel):
    """Google Gemini AI model implementation."""

    def __init__(self, api_key: str, model_name: str = "gemini-3-pro-preview") -> None:
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name
        logger.info("Initialized Gemini model: {}", model_name)

    async def generate_text(self, prompt: str, max_tokens: int = 8000) -> str | None:
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                config={"max_output_tokens": max_tokens},
            )
            return response.text
        except Exception as exc:
            logger.error("Gemini generation failed: {}", type(exc).__name__)
            return None


class ClaudeModel(AIModel):
    """Anthropic Claude AI model implementation."""

    def __init__(
        self, api_key: str, model_name: str = "claude-sonnet-4-5-20250929"
    ) -> None:
        self.client = AsyncAnthropic(api_key=api_key)
        self.model_name = model_name
        logger.info("Initialized Claude model: {}", model_name)

    async def generate_text(self, prompt: str, max_tokens: int = 8000) -> str | None:
        try:
            message = await self.client.messages.create(
                model=self.model_name,
                max_tokens=max_tokens,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            return message.content[0].text
        except Exception as exc:
            logger.error("Claude generation failed: {}", type(exc).__name__)
            return None


class OpenAIModel(AIModel):
    """OpenAI Responses API using an official API key, not a browser session."""

    def __init__(
        self,
        api_key: str,
        model_name: str = "gpt-6.1-sol",
        reasoning_effort: str = "low",
        timeout_seconds: float = 120.0,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.api_key = api_key
        self.model_name = model_name
        self.reasoning_effort = reasoning_effort
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        logger.info("Initialized OpenAI model: {}", model_name)

    @staticmethod
    def _output_text(data: dict) -> str | None:
        # Reasoning items can precede the message. Never return partial answers or
        # a refusal as a successful summary (including mixed text/refusal output).
        if data.get("status") != "completed" or data.get("error"):
            return None
        parts = []
        for item in data.get("output", []):
            if item.get("type") != "message":
                continue
            if item.get("status") not in (None, "completed"):
                return None
            for block in item.get("content", []):
                if block.get("type") == "refusal":
                    return None
                if block.get("type") == "output_text":
                    value = block.get("text")
                    if isinstance(value, str):
                        parts.append(value)
        return "\n".join(parts).strip() or None

    async def generate_text(self, prompt: str, max_tokens: int = 8000) -> str | None:
        payload = {
            "model": self.model_name,
            "input": prompt,
            "max_output_tokens": max_tokens,
            "reasoning": {"effort": self.reasoning_effort},
            "store": False,
        }
        try:
            # This deadline includes connect, upload, response, retry backoff, and
            # all attempts. Per-operation HTTP timeouts alone are not a deadline.
            async with asyncio.timeout(self.timeout_seconds):
                async with httpx.AsyncClient(
                    transport=self.transport,
                    timeout=httpx.Timeout(
                        self.timeout_seconds, connect=min(10.0, self.timeout_seconds)
                    ),
                ) as client:
                    for attempt in range(3):
                        try:
                            response = await client.post(
                                "https://api.openai.com/v1/responses",
                                headers={"Authorization": f"Bearer {self.api_key}"},
                                json=payload,
                            )
                        except (httpx.TimeoutException, httpx.TransportError):
                            if attempt == 2:
                                raise
                            await asyncio.sleep(0.5 * (2**attempt))
                            continue
                        if response.is_error:
                            # Do not log response bodies: they may include the key
                            # or transcript. Exhausted billing/quota is not retryable.
                            quota_exhausted = False
                            if response.status_code == 429:
                                try:
                                    error = response.json().get("error", {})
                                    exhausted_codes = {
                                        "insufficient_quota",
                                        "credit_balance_exhausted",
                                    }
                                    quota_exhausted = (
                                        error.get("code") in exhausted_codes
                                        or error.get("type") in exhausted_codes
                                    )
                                except (ValueError, AttributeError):
                                    pass
                            transient = (
                                response.status_code in (408, 409, 429)
                                or response.status_code >= 500
                            )
                            if transient and not quota_exhausted and attempt < 2:
                                await asyncio.sleep(0.5 * (2**attempt))
                                continue
                            logger.error(
                                "OpenAI generation failed: HTTP {}",
                                response.status_code,
                            )
                            return None
                        text = self._output_text(response.json())
                        if text is None:
                            logger.error("OpenAI generation failed: unusable_output")
                        return text
        except Exception as exc:
            logger.error("OpenAI generation failed: {}", type(exc).__name__)
        return None


def create_ai_model() -> AIModel:
    """Select an explicit provider, or keep legacy auto priority, then OpenAI.

    Auto selects by key presence, not key validity. No silent provider switching
    occurs after a request fails; set AI_PROVIDER to override stale other keys.
    """
    settings = get_settings()
    provider = settings.ai_provider
    if provider == "auto":
        if settings.google_api_key:
            provider = "gemini"
        elif settings.anthropic_api_key:
            provider = "claude"
        elif settings.openai_api_key:
            provider = "openai"
        else:
            raise ValueError(
                "No AI model API key provided. Set GOOGLE_API_KEY, ANTHROPIC_API_KEY or OPENAI_API_KEY"
            )
    if provider == "gemini":
        if not settings.google_api_key:
            raise ValueError("AI_PROVIDER=gemini requires GOOGLE_API_KEY")
        return GeminiModel(
            api_key=settings.google_api_key, model_name=settings.gemini_model
        )
    if provider == "claude":
        if not settings.anthropic_api_key:
            raise ValueError("AI_PROVIDER=claude requires ANTHROPIC_API_KEY")
        return ClaudeModel(
            api_key=settings.anthropic_api_key, model_name=settings.claude_model
        )
    if provider == "openai":
        if not settings.openai_api_key:
            raise ValueError("AI_PROVIDER=openai requires OPENAI_API_KEY")
        return OpenAIModel(
            api_key=settings.openai_api_key,
            model_name=settings.openai_model,
            reasoning_effort=settings.openai_reasoning_effort,
            timeout_seconds=settings.openai_timeout_seconds,
        )
    raise ValueError("AI_PROVIDER must be auto, openai, gemini or claude")
