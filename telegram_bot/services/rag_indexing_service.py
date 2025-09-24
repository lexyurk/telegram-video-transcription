"""Service handling meeting ingestion and vector indexing for RAG."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from chromadb import PersistentClient
from chromadb.utils import embedding_functions
from loguru import logger

from telegram_bot.config import get_settings
from telegram_bot.services.ai_model import AIModel, create_ai_model


@dataclass
class EpisodeChunk:
    """Represents a chunk of meeting transcript prepared for indexing."""

    chunk_id: str
    text: str
    summary: str
    meeting_id: str
    episode_id: str
    start_time: float | None
    end_time: float | None
    project_affinity: Dict[str, float]
    topics: List[str]
    metadata: Dict[str, Any]


@dataclass
class Episode:
    """Episode segmentation result used for indexing."""

    episode_id: str
    meeting_id: str
    start_time: float | None
    end_time: float | None
    text: str
    summary: str
    topics: List[str]
    project_affinity: Dict[str, float]


class RAGIndexingService:
    """Ingest meetings and maintain vector index for each user."""

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
        logger.info("Initialized RAG indexing service with model {}", self.embedding_model_name)

    def _collection_name(self, user_id: int) -> str:
        return f"user_{user_id}_meetings"

    def ensure_namespace(self, user_id: int) -> None:
        """Ensure a collection exists for the user."""
        collection_name = self._collection_name(user_id)
        if collection_name in [c.name for c in self.client.list_collections()]:
            return
        self.client.create_collection(name=collection_name, metadata={"user_id": str(user_id)})
        logger.info("Created vector namespace for user {}", user_id)

    def delete_namespace(self, user_id: int) -> None:
        """Delete vector collection and metadata for a user."""
        collection_name = self._collection_name(user_id)
        try:
            self.client.delete_collection(collection_name)
            logger.info("Deleted vector namespace for user {}", user_id)
        except Exception as exc:
            logger.warning("Failed to delete namespace {}: {}", collection_name, exc)

    def index_chunks(self, user_id: int, chunks: List[EpisodeChunk]) -> None:
        """Index prepared chunks for the user."""
        if not chunks:
            logger.info("No chunks to index for user {}", user_id)
            return

        self.ensure_namespace(user_id)
        collection = self.client.get_collection(
            name=self._collection_name(user_id),
            embedding_function=self.embedding_fn,
        )

        ids = [chunk.chunk_id for chunk in chunks]
        documents = [chunk.text for chunk in chunks]
        metadatas = [self._chunk_metadata(chunk) for chunk in chunks]

        try:
            collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            logger.info("Indexed {} chunks for user {}", len(chunks), user_id)
        except Exception as exc:
            logger.error("Failed to upsert chunks: {}", exc)
            raise

    def _chunk_metadata(self, chunk: EpisodeChunk) -> Dict[str, Any]:
        metadata = {
            "meeting_id": chunk.meeting_id,
            "episode_id": chunk.episode_id,
            "summary": chunk.summary,
            "project_affinity": json.dumps(chunk.project_affinity),
            "topics": chunk.topics,
        }
        metadata.update(chunk.metadata)
        if chunk.start_time is not None:
            metadata["start_time"] = chunk.start_time
        if chunk.end_time is not None:
            metadata["end_time"] = chunk.end_time
        return metadata

    async def label_episode_projects(self, text: str) -> Dict[str, float]:
        """Use LLM to label project affinity for an episode."""
        prompt = (
            "You are an expert assistant labeling meeting transcript segments with project relevance.\n"
            "Return JSON with project aliases mapped to confidence scores between 0 and 1.\n"
            "If no project is mentioned, return {}.\n\n"
            "Segment:\n"
            f"{text}\n\n"
            "JSON:\n"
        )
        response = await self.ai_model.generate_text(prompt)
        if not response:
            return {}
        try:
            if response.startswith("```"):
                lines = [line for line in response.splitlines() if not line.startswith("```")]
                response = "\n".join(lines)
            return json.loads(response)
        except Exception as exc:
            logger.warning("Failed to parse project affinity JSON: {}", exc)
            return {}

    async def ingest_meeting(
        self,
        user_id: int,
        meeting_id: str,
        transcript: str,
        meeting_metadata: Dict[str, Any],
    ) -> List[Episode]:
        """Chunk, summarize, and label a meeting transcript."""

        logger.info("Ingesting meeting {} for user {}", meeting_id, user_id)
        # Placeholder implementation: treat entire transcript as single episode
        summary_prompt = f"Summarize this meeting transcript in 3 sentences:\n\n{transcript}"
        summary = await self.ai_model.generate_text(summary_prompt) or ""
        project_affinity = await self.label_episode_projects(transcript)
        topics = list(project_affinity.keys())

        episode = Episode(
            episode_id=f"{meeting_id}:episode:0",
            meeting_id=meeting_id,
            start_time=None,
            end_time=None,
            text=transcript,
            summary=summary,
            topics=topics,
            project_affinity=project_affinity,
        )

        chunk = EpisodeChunk(
            chunk_id=f"{meeting_id}:chunk:0",
            text=transcript,
            summary=summary,
            meeting_id=meeting_id,
            episode_id=episode.episode_id,
            start_time=None,
            end_time=None,
            project_affinity=project_affinity,
            topics=topics,
            metadata=meeting_metadata,
        )

        self.index_chunks(user_id, [chunk])
        return [episode]


