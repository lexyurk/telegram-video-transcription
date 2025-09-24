"""Service orchestrating retrieval and answer generation for RAG queries."""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from chromadb import PersistentClient
from chromadb.utils import embedding_functions
from loguru import logger

from telegram_bot.config import get_settings
from telegram_bot.services.ai_model import AIModel, create_ai_model
from telegram_bot.services.rag_intent_parser import ParsedIntent


class RAGQueryService:
    """Execute RAG queries using vector search and structured metadata."""

    def __init__(
        self,
        embedding_model: Optional[str] = None,
        client: Optional[PersistentClient] = None,
        ai_model: Optional[AIModel] = None,
    ) -> None:
        settings = get_settings()
        self.base_path = settings.temp_dir
        self.embedding_model_name = embedding_model or "sentence-transformers/roberta-base-nli-mean-tokens"
        self.client = client or PersistentClient(path=f"{self.base_path}/chroma")
        self.ai_model = ai_model or create_ai_model()
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model_name
        )
        logger.info("Initialized RAG query service with model {}", self.embedding_model_name)

    def _collection_name(self, user_id: int) -> str:
        return f"user_{user_id}_meetings"

    async def answer(self, user_id: int, intent: ParsedIntent, message: str) -> str | None:
        """Retrieve relevant chunks and synthesize answer."""
        try:
            collection = self.client.get_collection(
                name=self._collection_name(user_id),
                embedding_function=self.embedding_fn,
            )
        except Exception:
            logger.warning("No collection found for user {}; returning fallback", user_id)
            return None

        query_filter = self._build_filter(intent)
        logger.debug("Query filter: {}", query_filter)

        results = collection.query(
            query_texts=[message],
            n_results=8,
            where=query_filter or None,
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]

        if not documents:
            logger.info("No RAG documents retrieved for user {}", user_id)
            return None

        prompt = self._build_answer_prompt(message, intent, documents, metadatas)
        response = await self.ai_model.generate_text(prompt)
        if not response:
            return None
        return response.strip()

    def _build_filter(self, intent: ParsedIntent) -> Dict[str, Any] | None:
        filters: Dict[str, Any] = {}

        project_ids = [
            project.get("alias")
            for project in intent.projects
            if project.get("confidence", 0) >= 0.6 and project.get("alias")
        ]
        if project_ids:
            filters["project_tags"] = {
                "$in": project_ids,
            }

        if intent.date_ranges:
            filters["meeting_date"] = {
                "$in": [rng.get("start") for rng in intent.date_ranges if rng.get("start")]
            }

        return filters or None

    def _build_answer_prompt(
        self,
        message: str,
        intent: ParsedIntent,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> str:
        language_hint = self._infer_language(message)
        context_snippets = []
        for doc, meta in zip(documents, metadatas):
            project_affinity = meta.get("project_affinity")
            try:
                if isinstance(project_affinity, str):
                    project_affinity = json.loads(project_affinity)
            except json.JSONDecodeError:
                project_affinity = {}
            snippet = {
                "text": doc,
                "summary": meta.get("summary"),
                "meeting_date": meta.get("meeting_date"),
                "meeting_id": meta.get("meeting_id"),
                "participants": meta.get("participants"),
                "project_affinity": project_affinity,
                "project_tags": (meta.get("project_tags") or "").split(","),
                "project_tags_norm": (meta.get("project_tags_norm") or "").split(","),
                "primary_project": meta.get("primary_project"),
                "primary_project_score": meta.get("primary_project_score"),
            }
            context_snippets.append(snippet)

        return json.dumps(
            {
                "instruction": (
                    "You are assisting the user in searching their meeting transcripts. "
                    "Always respond in the same language as `user_message` (language hint: "
                    f"{language_hint}). Format strictly as follows:\n"
                    "Цитаты:\n"
                    "- \"<quote 1>\" — <speaker or 'Участник'> (<meeting_date>)\n"
                    "- ... (add as many relevant quotes as needed)\n"
                    "Резюме: <2-3 sentence synthesis based only on the quotes above>.\n"
                    "Rules: Quotes must be exact sentences copied verbatim from `text`. Include the speaker name"
                    " if it appears at the start of the quoted sentence (e.g., 'Sasha: ...'). If no speaker is"
                    " present, label as 'Участник'. Always include the meeting_date in parentheses. If no relevant"
                    " quotes exist, write `Цитаты: отсутствуют` and explain in the summary why. Never invent information"
                    " that is not present in the provided snippets."
                ),
                "user_message": message,
                "intent": intent.__dict__,
                "snippets": context_snippets,
                "user_language_hint": language_hint,
            },
            indent=2,
        )

    def _infer_language(self, message: str) -> str:
        """Very lightweight language hint used for prompting the LLM."""

        for char in message:
            if "а" <= char.lower() <= "я" or char in "ёЁ":
                return "Russian"
        return "English"


