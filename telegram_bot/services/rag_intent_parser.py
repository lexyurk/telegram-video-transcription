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

        response = await self.ai_model.generate_json(
            prompt,
            response_schema={
                "type": "object",
                "properties": {
                    "intent": {"type": "string"},
                    "projects": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "alias": {"type": "string"},
                                "confidence": {"type": "number"},
                            },
                        },
                    },
                    "date_ranges": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "start": {"type": "string"},
                                "end": {"type": "string"},
                            },
                        },
                    },
                    "topics": {"type": "array", "items": {"type": "string"}},
                    "follow_up": {"type": "boolean"},
                    "confidence": {"type": "number"},
                    "uncertainty_reason": {"type": "string"},
                },
            },
        )

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
            parsed = ParsedIntent(
                intent=response.get("intent", "general_question"),
                projects=response.get("projects", []),
                date_ranges=response.get("date_ranges", []),
                topics=response.get("topics", []),
                follow_up=response.get("follow_up", False),
                confidence=float(response.get("confidence", 0.0)),
                uncertainty_reason=response.get("uncertainty_reason"),
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
            "You are an intent classification assistant for a meeting knowledge base."
            " Your job is to take a Telegram message and convert it into a structured representation."
            " Output must conform to the provided JSON schema."
            "\n\nSchema:\n"
            "{\n"
            "  \"intent\": string,\n"
            "  \"projects\": array of objects with properties:\n"
            "    {\"alias\": string, \"confidence\": number},\n"
            "  \"date_ranges\": array of objects with properties:\n"
            "    {\"start\": string, \"end\": string},\n"
            "  \"topics\": array of strings,\n"
            "  \"follow_up\": boolean,\n"
            "  \"confidence\": number,\n"
            "  \"uncertainty_reason\": string | null\n"
            "}\n\n"
            "Rules:\n"
            "- Extract project aliases even if referenced indirectly (\"our CRM project\" -> \"CRM\").\n"
            "- Detect relative dates and return normalized expressions (\"yesterday\", \"last Monday\").\n"
            "- If unsure about intent or projects, set \"confidence\" < 0.5 and explain via \"uncertainty_reason\".\n"
            "- If this message references prior context implicitly (\"that project\"), reuse project/date hints from previous intent when provided.\n\n"
            f"{previous_section}"
            "Examples:\n"
            f"{example_section}\n\n"
            "Message:\n"
            f"{message}\n\n"
        )
