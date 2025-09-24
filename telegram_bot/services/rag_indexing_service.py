"""Service handling meeting ingestion and vector indexing for RAG."""

import hashlib
import json
import re
import textwrap
from dataclasses import dataclass
from typing import Any

from chromadb import PersistentClient
from chromadb.utils import embedding_functions
from loguru import logger

from telegram_bot.config import get_settings
from telegram_bot.services.ai_model import AIModel, create_ai_model
from telegram_bot.services.rag_storage_service import RAGStorageService


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
    project_affinity: dict[str, float]
    topics: list[str]
    metadata: dict[str, Any]


@dataclass
class EpisodePlanSegment:
    """Structured episode plan data returned by the LLM."""

    order: int
    title: str
    summary: str
    topics: list[str]
    projects: list[dict[str, Any]]
    start_anchor: str
    end_anchor: str
    confidence: float
    notes: str | None = None


@dataclass
class Episode:
    """Episode segmentation result used for indexing."""

    episode_id: str
    meeting_id: str
    start_time: float | None
    end_time: float | None
    start_char: int
    end_char: int
    text: str
    summary: str
    topics: list[str]
    project_affinity: dict[str, float]


class RAGIndexingService:
    """Ingest meetings and maintain vector index for each user."""

    def __init__(
        self,
        embedding_model: str | None = None,
        client: PersistentClient | None = None,
        ai_model: AIModel | None = None,
        storage: RAGStorageService | None = None,
    ) -> None:
        settings = get_settings()
        self.base_path = settings.temp_dir
        self.embedding_model_name = embedding_model or settings.rag_embedding_model
        self.client = client or PersistentClient(path=f"{self.base_path}/chroma")
        self.ai_model = ai_model or create_ai_model()
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model_name
        )
        self.storage = storage or RAGStorageService()
        logger.info("Initialized RAG indexing service with model {}", self.embedding_model_name)

    async def generate_segmentation_plan(
        self,
        meeting_id: str,
        transcript: str,
        forced: bool = False,
    ) -> list[EpisodePlanSegment]:
        """Generate or reuse an LLM-produced episode plan for the transcript."""

        transcript_hash = hashlib.sha256(transcript.encode("utf-8")).hexdigest()
        cached = self.storage.get_segmentation_plan(meeting_id)
        if cached and not forced:
            if cached.get("transcript_hash") == transcript_hash:
                try:
                    return [EpisodePlanSegment(**segment) for segment in cached["segments"]]
                except Exception as exc:
                    logger.warning("Failed to deserialize cached segmentation plan: {}", exc)

        prompt = self._build_segmentation_prompt(transcript)
        response = await self.ai_model.generate_text(prompt)
        if not response:
            logger.warning("Segmentation LLM returned empty response")
            return []

        plan = self._parse_segmentation_response(response)
        if plan:
            self.storage.save_segmentation_plan(
                meeting_id=meeting_id,
                transcript_hash=transcript_hash,
                plan=[segment.__dict__ for segment in plan],
            )
        return plan

    def _build_segmentation_prompt(self, transcript: str) -> str:
        trimmed = transcript.strip()
        return textwrap.dedent(
            f"""
            You are an expert meeting analyst. Analyze the following full meeting transcript and split it into coherent episodes.
 
             Instructions:
             - Each episode should focus on a project, topic, or major discussion theme.
             - Even if a project is only named once, keep subsequent related discussion under the same episode until the topic clearly changes.
             - When multiple projects are discussed sequentially, produce separate episodes in chronological order.
             - Include neutral/general-business episodes if the discussion is not tied to a project.
             - For each episode, capture:
               * order (1-based)
               * title (short human-friendly summary)
               * summary (2-3 sentences)
               * topics (list of keywords)
               * projects (array of objects with alias, confidence 0-1, and supporting quote)
               * start_anchor: quote the first sentence or distinctive phrase of the episode
               * end_anchor: quote the last sentence or distinctive phrase of the episode
               * confidence: overall confidence that the segmentation is correct (0-1)
               * notes: optional clarifications or open questions
            - Respond strictly as JSON with schema {{"episodes": [ ... ]}}.
 
             Transcript:
             {trimmed}
             """
        ).strip()

    def _parse_segmentation_response(self, response: str) -> list[EpisodePlanSegment]:
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = "\n".join(line for line in cleaned.splitlines() if not line.startswith("```"))
        try:
            data = json.loads(cleaned)
            episodes = data.get("episodes", [])
            plan = []
            for episode in episodes:
                try:
                    plan.append(
                        EpisodePlanSegment(
                            order=int(episode.get("order", len(plan) + 1)),
                            title=episode.get("title", "Unnamed Episode"),
                            summary=episode.get("summary", ""),
                            topics=episode.get("topics", []) or [],
                            projects=episode.get("projects", []) or [],
                            start_anchor=episode.get("start_anchor", ""),
                            end_anchor=episode.get("end_anchor", ""),
                            confidence=float(episode.get("confidence", 0.5)),
                            notes=episode.get("notes"),
                        )
                    )
                except Exception as exc:
                    logger.warning("Skipping malformed episode entry: {}", exc)
            return plan
        except json.JSONDecodeError as exc:
            logger.warning("Failed to parse segmentation response as JSON: {}", exc)
            return []

    def _find_anchor_positions(self, transcript: str, start_anchor: str, end_anchor: str) -> tuple[int, int]:
        """Locate start and end anchors within the transcript, returning char indices."""

        def _search(anchor: str, default: int) -> int:
            if not anchor:
                return default
            pattern = re.escape(anchor.strip())
            match = re.search(pattern, transcript, flags=re.IGNORECASE)
            if match:
                return match.start()
            return default

        start = _search(start_anchor, 0)
        end = _search(end_anchor, len(transcript))
        if end < start:
            end = len(transcript)
        return start, end

    def _split_transcript_by_plan(
        self,
        transcript: str,
        plan: list[EpisodePlanSegment],
    ) -> list[Episode]:
        episodes: list[Episode] = []
        last_end = 0
        sentences = re.split(r"(?<=[.!?])\s+", transcript)

        def expand_to_sentence_boundary(idx: int) -> int:
            if idx <= 0:
                return 0
            if idx >= len(transcript):
                return len(transcript)
            for match in re.finditer(r"[.!?]\s+", transcript):
                if match.start() >= idx:
                    return match.start()
            return idx

        for segment in plan:
            start_char, end_char = self._find_anchor_positions(
                transcript, segment.start_anchor, segment.end_anchor
            )
            if start_char < last_end:
                start_char = last_end
            if end_char <= start_char:
                end_char = len(transcript)
            start_char = expand_to_sentence_boundary(start_char)
            end_char = expand_to_sentence_boundary(end_char)
            text_slice = transcript[start_char:end_char].strip()
            if not text_slice:
                continue
            episodes.append(
                Episode(
                    episode_id="",
                    meeting_id="",
                    start_time=None,
                    end_time=None,
                    start_char=start_char,
                    end_char=end_char,
                    text=text_slice,
                    summary=segment.summary,
                    topics=segment.topics or [segment.title],
                    project_affinity={
                        proj.get("alias", ""): float(proj.get("confidence", 0.0))
                        for proj in segment.projects or []
                        if proj.get("alias")
                    },
                )
            )
            last_end = end_char
        if not episodes:
            episodes.append(
                Episode(
                    episode_id="",
                    meeting_id="",
                    start_time=None,
                    end_time=None,
                    start_char=0,
                    end_char=len(transcript),
                    text=transcript,
                    summary="",
                    topics=[],
                    project_affinity={},
                )
            )
        return episodes

    def _collection_name(self, user_id: int) -> str:
        return f"user_{user_id}_meetings"

    def ensure_namespace(self, user_id: int) -> None:
        """Ensure a collection exists for the user."""
        collection_name = self._collection_name(user_id)
        existing = [c.name for c in self.client.list_collections()]
        if collection_name in existing:
            return
        self.client.create_collection(
            name=collection_name,
            metadata={"user_id": str(user_id)},
            embedding_function=self.embedding_fn,
        )
        logger.info("Created vector namespace for user {}", user_id)

    def delete_namespace(self, user_id: int) -> None:
        """Delete vector collection and metadata for a user."""
        collection_name = self._collection_name(user_id)
        try:
            self.client.delete_collection(collection_name)
            logger.info("Deleted vector namespace for user {}", user_id)
        except Exception as exc:
            logger.warning("Failed to delete namespace {}: {}", collection_name, exc)

    def index_chunks(self, user_id: int, chunks: list[EpisodeChunk]) -> None:
        """Index prepared chunks for the user."""
        if not chunks:
            logger.info("No chunks to index for user {}", user_id)
            return

        self.ensure_namespace(user_id)
        collection = self.client.get_collection(
            name=self._collection_name(user_id),
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
            "topics": ",".join(chunk.topics),
        }
        metadata.update(chunk.metadata)
        if chunk.start_time is not None:
            metadata["start_time"] = chunk.start_time
        if chunk.end_time is not None:
            metadata["end_time"] = chunk.end_time

        project_items = sorted(
            (
                (alias, float(score), self._normalize_alias(alias))
                for alias, score in chunk.project_affinity.items()
                if alias
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        if project_items:
            top_alias, top_score, top_norm = project_items[0]
            metadata["primary_project"] = top_alias
            metadata["primary_project_norm"] = top_norm
            metadata["primary_project_score"] = top_score
            metadata["project_tags"] = ",".join(alias for alias, _, _ in project_items)
            metadata["project_tags_norm"] = ",".join(norm for _, _, norm in project_items)
        return metadata

    def _normalize_alias(self, alias: str) -> str:
        cleaned = re.sub(r"[^a-z0-9]+", "_", alias.lower())
        return cleaned.strip("_")

    async def label_episode_projects(self, text: str) -> dict[str, float]:
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
        meeting_metadata: dict[str, Any],
    ) -> list[Episode]:
        """Segment, summarize, and index a meeting transcript."""

        logger.info("Ingesting meeting {} for user {}", meeting_id, user_id)
        plan = await self.generate_segmentation_plan(meeting_id, transcript)
        episodes = self._split_transcript_by_plan(transcript, plan)

        indexed_chunks: list[EpisodeChunk] = []
        for idx, episode in enumerate(episodes):
            episode_id = f"{meeting_id}:episode:{idx}"
            episode.episode_id = episode_id
            episode.meeting_id = meeting_id

            if not episode.summary:
                summary_prompt = textwrap.dedent(
                    f"""
                    Summarize this meeting episode in 2 sentences, focusing on decisions and owners:

                    {episode.text}
                    """
                )
                episode.summary = await self.ai_model.generate_text(summary_prompt) or ""

            if not episode.project_affinity:
                episode.project_affinity = await self.label_episode_projects(episode.text)

            chunk = EpisodeChunk(
                chunk_id=f"{meeting_id}:chunk:{idx}",
                text=episode.text,
                summary=episode.summary,
                meeting_id=meeting_id,
                episode_id=episode_id,
                start_time=episode.start_time,
                end_time=episode.end_time,
                project_affinity=episode.project_affinity,
                topics=episode.topics,
                metadata={
                    **meeting_metadata,
                    "start_char": episode.start_char,
                    "end_char": episode.end_char,
                },
            )
            indexed_chunks.append(chunk)

            self.storage.upsert_projects(user_id, episode.project_affinity)

        self.index_chunks(user_id, indexed_chunks)
        return episodes


