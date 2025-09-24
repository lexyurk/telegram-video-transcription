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

        project_ids = [project.get("alias") for project in intent.projects if project.get("confidence", 0) >= 0.6]
        if project_ids:
            filters["project_affinity"] = {"$contains": project_ids}

        if intent.date_ranges:
            filters["meeting_date"] = {"$in": [rng.get("start") for rng in intent.date_ranges if rng.get("start")]
            }

        return filters or None

    def _build_answer_prompt(
        self,
        message: str,
        intent: ParsedIntent,
        documents: List[str],
        metadatas: List[Dict[str, Any]],
    ) -> str:
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
                "participants": meta.get("participants"),
                "project_affinity": project_affinity,
            }
            context_snippets.append(snippet)

        return json.dumps(
            {
                "instruction": "Use the provided snippets to answer the user's question about their meetings. Cite meeting dates and highlight relevant projects.",
                "user_message": message,
                "intent": intent.__dict__,
                "snippets": context_snippets,
            },
            indent=2,
        )


