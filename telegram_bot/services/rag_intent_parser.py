"""Intent parsing service for free-form RAG queries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, List, Optional

from loguru import logger

from telegram_bot.services.ai_model import AIModel, create_ai_model


@dataclass
class ParsedIntent:
    """Structured representation of a user RAG query."""

    intent: str
    projects: List[dict]
    date_ranges: List[dict]
    topics: List[str]
    follow_up: bool
    confidence: float
    uncertainty_reason: Optional[str]


class RAGIntentParser:
    """Parse free-form Telegram messages into structured RAG intents."""

    def __init__(self, ai_model: AIModel | None = None) -> None:
        if ai_model is not None:
            self.ai_model = ai_model
        else:
            self.ai_model = create_ai_model()
        logger.info("RAG intent parser initialized")

    async def parse(self, message: str, context: Optional[dict[str, Any]] = None) -> ParsedIntent:
        """Parse a free-form message into a structured intent."""

        context = context or {}
        prompt = self._build_prompt(message, context)

        logger.debug("Parsing RAG intent for message: {}", message[:200])

        response = await self.ai_model.generate_text(prompt)

        if not response:
            logger.warning("Intent parser returned empty response; using fallback")
            return ParsedIntent(
                intent="general_question",
                projects=[],
                date_ranges=[],
                topics=[],
                follow_up=False,
                confidence=0.0,
                uncertainty_reason="empty_response",
            )

        try:
            data = self._extract_json(response)
            parsed = ParsedIntent(
                intent=data.get("intent", "general_question"),
                projects=data.get("projects", []),
                date_ranges=data.get("date_ranges", []),
                topics=data.get("topics", []),
                follow_up=data.get("follow_up", False),
                confidence=float(data.get("confidence", 0.0)),
                uncertainty_reason=data.get("uncertainty_reason"),
            )
            logger.debug("Parsed intent: {}", parsed)
            return parsed
        except Exception as exc:
            logger.warning("Failed to parse intent response: {}", exc)
            return ParsedIntent(
                intent="general_question",
                projects=[],
                date_ranges=[],
                topics=[],
                follow_up=False,
                confidence=0.0,
                uncertainty_reason="parse_error",
            )

    def _build_prompt(self, message: str, context: dict[str, Any]) -> str:
        examples = context.get("examples", [])
        previous = context.get("previous_intent")

        example_section = "\n".join(examples)
        previous_section = f"Previous intent JSON: {previous}\n" if previous else ""

        return (
            "You are an intent classification assistant for a meeting knowledge base.\n"
            "Your job is to take a Telegram message and convert it into a strict JSON object with this schema:\n\n"
            "{\n"
            "  \"intent\": \"project_summary\" | \"date_summary\" | \"general_question\" | \"action_items\" | \"topics_overview\" | \"clarification_needed\",\n"
            "  \"projects\": [{\"alias\": string, \"confidence\": float}],\n"
            "  \"date_ranges\": [{\"start\": ISO8601/date expression, \"end\": ISO8601/date expression}],\n"
            "  \"topics\": [string],\n"
            "  \"follow_up\": bool,\n"
            "  \"confidence\": float between 0 and 1,\n"
            "  \"uncertainty_reason\": string | null\n"
            "}\n\n"
            "Rules:\n"
            "- Always return valid JSON only. No markdown, no commentary.\n"
            "- Extract project aliases even if referenced indirectly (\"our CRM project\" -> \"CRM\").\n"
            "- Detect relative dates and return normalized expressions (\"yesterday\", \"last Monday\").\n"
            "- If unsure about intent or projects, set \"confidence\" < 0.5 and explain via \"uncertainty_reason\".\n"
            "- If this message references prior context implicitly (\"that project\"), reuse project/date hints from previous intent when provided.\n\n"
            f"{previous_section}"
            "Examples:\n"
            f"{example_section}\n\n"
            "Message:\n"
            f"{message}\n\n"
            "Return only JSON."
        )

    def _extract_json(self, response: str) -> dict[str, Any]:
        response = response.strip()
        if response.startswith("```"):
            # Handle fenced code blocks
            lines = [line for line in response.splitlines() if not line.startswith("```")]
            response = "\n".join(lines)
        import json

        return json.loads(response)

