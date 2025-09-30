"""Service orchestrating retrieval and answer generation for RAG queries."""

import json
from typing import Any, Optional

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
        self.embedding_model_name = embedding_model or settings.rag_embedding_model
        self.client = client or PersistentClient(path=f"{self.base_path}/chroma")
        self.ai_model = ai_model or create_ai_model()
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model_name
        )
        self.retrieval_k = settings.rag_retrieval_k
        self.similarity_threshold = settings.rag_similarity_threshold
        logger.info(
            "Initialized RAG query service with model {} (k={}, threshold={})",
            self.embedding_model_name,
            self.retrieval_k,
            self.similarity_threshold,
        )

    def _collection_name(self, user_id: int) -> str:
        """Get collection name for user."""
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

        # Build filter from intent
        query_filter = self._build_filter(intent)
        logger.debug("Query filter: {}", query_filter)

        # Adjust retrieval count based on query complexity
        n_results = self._determine_retrieval_count(intent, message)

        # Perform vector search
        results = collection.query(
            query_texts=[message],
            n_results=n_results,
            where=query_filter or None,
        )

        documents = results.get("documents", [[]])[0]
        metadatas = results.get("metadatas", [[]])[0]
        distances = results.get("distances", [[]])[0]

        if not documents:
            logger.info("No RAG documents retrieved for user {}", user_id)
            return None

        # Apply similarity threshold filtering
        filtered_results = self._filter_by_similarity(documents, metadatas, distances)

        if not filtered_results:
            logger.info("All retrieved documents filtered out by similarity threshold")
            return None

        logger.info(
            "Retrieved {} chunks for user {} (filtered from {} by similarity threshold)",
            len(filtered_results),
            user_id,
            len(documents),
        )

        # Generate answer
        prompt = self._build_answer_prompt(message, intent, filtered_results)
        response = await self.ai_model.generate_text(prompt, max_tokens=8000)
        if not response:
            return None
        return response.strip()

    def _determine_retrieval_count(self, intent: ParsedIntent, message: str) -> int:
        """Determine optimal retrieval count based on query characteristics."""
        base_k = self.retrieval_k

        # Increase for queries with multiple projects
        if len(intent.projects) > 1:
            base_k += 4

        # Increase for action item queries (need more context)
        if intent.intent in ["action_items", "topics_overview"]:
            base_k += 4

        # Increase for broad date ranges
        if len(intent.date_ranges) > 1:
            base_k += 2

        # Increase for longer queries (more specific)
        if len(message.split()) > 15:
            base_k += 2

        return min(base_k, 20)  # Cap at 20

    def _filter_by_similarity(
        self,
        documents: list[str],
        metadatas: list[dict[str, Any]],
        distances: list[float],
    ) -> list[dict[str, Any]]:
        """Filter results by similarity threshold and prepare for prompting."""
        filtered = []
        for doc, meta, dist in zip(documents, metadatas, distances):
            # ChromaDB uses L2 distance; lower is better
            # Typical good matches are < 0.7
            if dist <= self.similarity_threshold:
                filtered.append({
                    "text": doc,
                    "metadata": meta,
                    "distance": dist,
                })
        return filtered

    def _build_filter(self, intent: ParsedIntent) -> dict[str, Any] | None:
        """Build metadata filter from parsed intent."""
        filters: dict[str, Any] = {}

        # Filter by projects (if high confidence)
        project_ids = [
            project.get("alias")
            for project in intent.projects
            if project.get("confidence", 0) >= 0.5 and project.get("alias")
        ]
        if project_ids:
            # Use normalized project names for filtering
            normalized = [p.lower().replace(" ", "_") for p in project_ids]
            filters["primary_project_norm"] = {"$in": normalized}

        # Filter by date if available
        if intent.date_ranges:
            # For simplicity, use first date range
            date_range = intent.date_ranges[0]
            if date_range.get("start"):
                filters["meeting_date"] = {"$gte": date_range["start"]}

        return filters if filters else None

    def _build_answer_prompt(
        self,
        message: str,
        intent: ParsedIntent,
        results: list[dict[str, Any]],
    ) -> str:
        """Build language-agnostic answer prompt with retrieved context."""
        language = self._infer_language(message)

        # Prepare context snippets with metadata
        context_snippets = []
        for idx, result in enumerate(results):
            doc = result["text"]
            meta = result["metadata"]

            # Parse project affinity
            project_affinity = meta.get("project_affinity", "{}")
            try:
                if isinstance(project_affinity, str):
                    project_affinity = json.loads(project_affinity)
            except json.JSONDecodeError:
                project_affinity = {}

            snippet = {
                "index": idx + 1,
                "text": doc,
                "summary": meta.get("summary", ""),
                "meeting_date": meta.get("meeting_date", "unknown"),
                "meeting_id": meta.get("meeting_id", ""),
                "participants": meta.get("participants", ""),
                "projects": list(project_affinity.keys()),
                "primary_project": meta.get("primary_project", ""),
                "topics": meta.get("topics", "").split(",") if meta.get("topics") else [],
                "distance": result.get("distance", 0),
            }
            context_snippets.append(snippet)

        # Build format instructions based on language
        if language == "Russian":
            format_instruction = """
**ФОРМАТ ОТВЕТА:**

Цитаты:
- "[точная цитата 1]" — спикер или 'Участник' (дата встречи, проект)
- "[точная цитата 2]" — спикер или 'Участник' (дата встречи, проект)
[добавьте столько цитат, сколько необходимо для полного ответа]

Резюме:
[2-4 предложения, синтезирующие информацию из цитат выше. Включите:
- Ключевые решения
- Action items с владельцами и дедлайнами (если есть)
- Требования или обсуждённые функции
- Статус или следующие шаги]

**ПРАВИЛА:**
- Цитаты должны быть точными предложениями из предоставленных фрагментов
- Всегда указывайте дату встречи и проект (если известен)
- Если спикер указан в тексте (например, "Саша: ..."), укажите его имя
- Если спикера нет в тексте, используйте "Участник"
- Если релевантных цитат нет, напишите "Цитаты: отсутствуют" и объясните почему в резюме
- НЕ придумывайте информацию, которой нет в предоставленных фрагментах
"""
        else:
            format_instruction = """
**RESPONSE FORMAT:**

Quotes:
- "[exact quote 1]" — speaker or 'Participant' (meeting date, project)
- "[exact quote 2]" — speaker or 'Participant' (meeting date, project)
[add as many quotes as needed for complete answer]

Summary:
[2-4 sentences synthesizing the information from quotes above. Include:
- Key decisions made
- Action items with owners and deadlines (if any)
- Requirements or features discussed
- Status or next steps]

**RULES:**
- Quotes must be exact sentences copied verbatim from provided snippets
- Always include meeting date and project (if known)
- If speaker is mentioned in text (e.g., "Sarah: ..."), include their name
- If no speaker in text, use "Participant"
- If no relevant quotes exist, write "Quotes: none found" and explain why in summary
- DO NOT invent information not present in provided snippets
"""

        # Build the full prompt
        prompt = f"""You are an assistant helping a user search their meeting transcripts and conversation history.

**USER QUESTION:**
{message}

**QUERY INTENT:**
- Type: {intent.intent}
- Projects mentioned: {", ".join([p.get("alias", "unknown") for p in intent.projects]) or "none"}
- Topics: {", ".join(intent.topics) or "none"}
- Follow-up question: {intent.follow_up}

**RETRIEVED CONTEXT:**
Below are {len(context_snippets)} relevant snippets from past meetings, ranked by relevance:

"""

        # Add each snippet
        for snippet in context_snippets:
            prompt += f"""
---
[Snippet {snippet['index']}]
Meeting: {snippet['meeting_date']} | Project: {snippet['primary_project'] or 'unspecified'} | Topics: {', '.join(snippet['topics'][:5])}
Relevance: {1 - snippet['distance']:.2f}

{snippet['text']}
---
"""

        prompt += f"\n{format_instruction}\n"

        # Add query-specific guidance
        if intent.intent == "action_items":
            prompt += "\n**FOCUS:** Extract all action items with owners and deadlines. Group by project if multiple.\n"
        elif intent.intent == "project_summary":
            prompt += "\n**FOCUS:** Provide comprehensive summary of all discussions, decisions, and status for the mentioned project(s).\n"
        elif "requirements" in message.lower() or "требования" in message.lower():
            prompt += "\n**FOCUS:** Extract all requirements, features, and specifications discussed. Include acceptance criteria if mentioned.\n"

        prompt += f"\n**YOUR ANSWER ({language}):**\n"

        return prompt

    def _infer_language(self, message: str) -> str:
        """Infer language from message for response formatting."""
        # Check for Cyrillic characters
        cyrillic_count = sum(1 for char in message if "а" <= char.lower() <= "я" or char in "ёЁ")
        if cyrillic_count > 3:
            return "Russian"
        return "English"