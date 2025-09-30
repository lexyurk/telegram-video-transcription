"""Intent parsing service for free-form RAG queries."""

import json
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from telegram_bot.services.ai_model import AIModel, create_ai_model


@dataclass
class ParsedIntent:
    """Structured representation of a user RAG query."""

    intent: str
    projects: list[dict]
    date_ranges: list[dict]
    topics: list[str]
    follow_up: bool
    confidence: float
    uncertainty_reason: Optional[str]


class RAGIntentParser:
    """Parse free-form Telegram messages into structured RAG intents."""

    def __init__(self, ai_model: Optional[AIModel] = None) -> None:
        self.ai_model = ai_model or create_ai_model()
        logger.info("RAG intent parser initialized")

    async def parse(self, message: str, context: Optional[dict[str, Any]] = None) -> ParsedIntent:
        """Parse a free-form message into a structured intent."""

        context = context or {}
        prompt = self._build_prompt(message, context)

        logger.debug("Parsing RAG intent for message: {}", message[:200])

        response = await self.ai_model.generate_text(prompt, max_tokens=1000)

        if not response:
            logger.warning("Intent parser returned empty response; using fallback")
            return self._fallback_intent("empty_response")

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
            return self._fallback_intent("parse_error")

    def _fallback_intent(self, reason: str) -> ParsedIntent:
        """Create fallback intent when parsing fails."""
        return ParsedIntent(
            intent="general_question",
            projects=[],
            date_ranges=[],
            topics=[],
            follow_up=False,
            confidence=0.0,
            uncertainty_reason=reason,
        )

    def _build_prompt(self, message: str, context: dict[str, Any]) -> str:
        """Build intent parsing prompt with examples."""
        previous = context.get("previous_intent")
        previous_section = f"\nPrevious intent: {json.dumps(previous)}\n" if previous else ""

        return f"""You are an intent classification assistant for a meeting knowledge base.
Convert the user message into a structured JSON object.

**SCHEMA:**
{{
  "intent": "project_summary" | "date_summary" | "general_question" | "action_items" | "topics_overview" | "requirements_query",
  "projects": [{{"alias": "ProjectName", "confidence": 0.0-1.0}}],
  "date_ranges": [{{"start": "date_expression", "end": "date_expression"}}],
  "topics": ["topic1", "topic2"],
  "follow_up": boolean,
  "confidence": 0.0-1.0,
  "uncertainty_reason": string | null
}}

**RULES:**
- Return ONLY valid JSON, no markdown or commentary
- Extract project names even from indirect references ("the banking app" → "banking")
- Detect relative dates ("yesterday", "last week", "this month")
- Set confidence < 0.5 if unsure, explain in uncertainty_reason
- For follow-up questions referencing "it", "that project", etc., mark follow_up=true{previous_section}

**EXAMPLES:**

Message: "What actions did we decide on for PiggyBank yesterday?"
{{
  "intent": "action_items",
  "projects": [{{"alias": "PiggyBank", "confidence": 0.95}}],
  "date_ranges": [{{"start": "yesterday", "end": "yesterday"}}],
  "topics": ["actions", "decisions"],
  "follow_up": false,
  "confidence": 0.9,
  "uncertainty_reason": null
}}

Message: "Remind me all requirements we discussed about piggybank from all calls"
{{
  "intent": "requirements_query",
  "projects": [{{"alias": "PiggyBank", "confidence": 0.9}}],
  "date_ranges": [],
  "topics": ["requirements", "features"],
  "follow_up": false,
  "confidence": 0.85,
  "uncertainty_reason": null
}}

Message: "What new project ideas did we discuss this week?"
{{
  "intent": "topics_overview",
  "projects": [],
  "date_ranges": [{{"start": "this week", "end": "today"}}],
  "topics": ["new projects", "ideas", "brainstorming"],
  "follow_up": false,
  "confidence": 0.8,
  "uncertainty_reason": null
}}

Message: "What are my action items from this week's discussions?"
{{
  "intent": "action_items",
  "projects": [],
  "date_ranges": [{{"start": "this week", "end": "today"}}],
  "topics": ["action items", "tasks", "assignments"],
  "follow_up": false,
  "confidence": 0.85,
  "uncertainty_reason": null
}}

**MESSAGE TO PARSE:**
{message}

**OUTPUT (JSON only):**
"""

    def _extract_json(self, response: str) -> dict[str, Any]:
        """Extract JSON from LLM response, handling markdown wrappers."""
        response = response.strip()
        if response.startswith("```"):
            lines = [line for line in response.splitlines() if not line.startswith("```")]
            response = "\n".join(lines).strip()
        return json.loads(response)