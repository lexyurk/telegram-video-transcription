"""Service handling meeting ingestion and vector indexing for RAG."""

import hashlib
import json
import re
import textwrap
from dataclasses import dataclass
from typing import Any, Optional

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
        embedding_model: Optional[str] = None,
        client: Optional[PersistentClient] = None,
        ai_model: Optional[AIModel] = None,
        storage: Optional[RAGStorageService] = None,
    ) -> None:
        settings = get_settings()
        self.base_path = settings.temp_dir
        self.embedding_model_name = embedding_model or settings.rag_embedding_model
        self.chunk_size = settings.rag_chunk_size
        self.chunk_overlap = settings.rag_chunk_overlap
        self.client = client or PersistentClient(path=f"{self.base_path}/chroma")
        self.ai_model = ai_model or create_ai_model()
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=self.embedding_model_name
        )
        self.storage = storage or RAGStorageService()
        logger.info(
            "Initialized RAG indexing service with model {} (chunk_size={}, overlap={})",
            self.embedding_model_name,
            self.chunk_size,
            self.chunk_overlap,
        )

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
        response = await self.ai_model.generate_text(prompt, max_tokens=16000)
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
        """Build an improved segmentation prompt with examples and clear length guidance."""
        trimmed = transcript.strip()
        word_count = len(trimmed.split())

        return textwrap.dedent(
            f"""
            You are an expert meeting analyst. Analyze the following meeting transcript and split it into coherent episodes.

            IMPORTANT GUIDELINES:
            1. Target episode length: 300-600 words (2-4 minutes of discussion)
            2. Each episode should focus on ONE specific topic, project discussion, or decision point
            3. When projects are mentioned, track them throughout the related discussion
            4. Include action items, decisions, and requirements as part of the relevant episode
            5. For multi-hour meetings, create 5-15 episodes depending on content

            EPISODE STRUCTURE:
            - order: Sequential number (1, 2, 3...)
            - title: Short descriptive title (5-8 words)
            - summary: 2-3 sentences capturing key points, decisions, and action items
            - topics: List of keywords (e.g., ["deployment", "database", "API design"])
            - projects: Array of {{"alias": "ProjectName", "confidence": 0.0-1.0, "quote": "supporting quote from transcript"}}
            - start_anchor: Copy the FIRST 10-20 words of the episode verbatim
            - end_anchor: Copy the LAST 10-20 words of the episode verbatim
            - confidence: Your confidence this segmentation is correct (0.0-1.0)
            - notes: Optional clarifications

            EXAMPLES OF GOOD EPISODES:

            Example 1 - Project Discussion:
            {{
              "order": 1,
              "title": "PiggyBank Project Requirements Review",
              "summary": "Team reviewed requirements for PiggyBank savings feature. Decided to implement automatic round-up transfers. Action item: Sarah to create API spec by Friday.",
              "topics": ["requirements", "savings", "API", "round-up transfers"],
              "projects": [{{"alias": "PiggyBank", "confidence": 0.95, "quote": "So for PiggyBank, we need to figure out the automatic savings logic"}}],
              "start_anchor": "Alright, let's talk about the PiggyBank feature requirements.",
              "end_anchor": "Great, so Sarah will have that spec ready by end of week.",
              "confidence": 0.9
            }}

            Example 2 - Action Items:
            {{
              "order": 2,
              "title": "Deployment Timeline and Owner Assignment",
              "summary": "Discussed deployment schedule for Q1. John will handle staging deployment on Monday. Production rollout scheduled for next Thursday with Alex as owner.",
              "topics": ["deployment", "timeline", "assignments", "Q1 planning"],
              "projects": [{{"alias": "Platform Migration", "confidence": 0.7, "quote": "the migration work needs to be deployed carefully"}}],
              "start_anchor": "Let's nail down the deployment timeline for next week.",
              "end_anchor": "Perfect, so Alex owns the production deployment next Thursday.",
              "confidence": 0.85
            }}

            TRANSCRIPT INFO:
            - Total words: {word_count}
            - Expected episodes: {max(3, word_count // 400)}

            Respond ONLY with valid JSON in this exact format:
            {{"episodes": [ ... ]}}

            TRANSCRIPT:
            {trimmed}
            """
        ).strip()

    def _parse_segmentation_response(self, response: str) -> list[EpisodePlanSegment]:
        """Parse LLM response into episode plan segments."""
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

    def _split_large_text_into_chunks(self, text: str, episode_id: str) -> list[tuple[str, str]]:
        """
        Split text into chunks with overlap, respecting sentence boundaries.

        Returns list of (chunk_text, chunk_id) tuples.
        """
        words = text.split()

        # If text fits in one chunk, return as-is
        if len(words) <= self.chunk_size:
            return [(text, f"{episode_id}:0")]

        # Split into sentences for better boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)

        chunks = []
        current_chunk = []
        current_word_count = 0
        chunk_idx = 0

        for sentence in sentences:
            sentence_words = len(sentence.split())

            # If adding this sentence exceeds chunk size and we have content, save chunk
            if current_word_count + sentence_words > self.chunk_size and current_chunk:
                chunk_text = " ".join(current_chunk)
                chunks.append((chunk_text, f"{episode_id}:{chunk_idx}"))
                chunk_idx += 1

                # Calculate overlap: keep last few sentences
                overlap_word_count = 0
                overlap_sentences = []
                for i in range(len(current_chunk) - 1, -1, -1):
                    sent = current_chunk[i]
                    sent_words = len(sent.split())
                    if overlap_word_count + sent_words <= self.chunk_overlap:
                        overlap_sentences.insert(0, sent)
                        overlap_word_count += sent_words
                    else:
                        break

                current_chunk = overlap_sentences
                current_word_count = overlap_word_count

            current_chunk.append(sentence)
            current_word_count += sentence_words

        # Add final chunk
        if current_chunk:
            chunk_text = " ".join(current_chunk)
            chunks.append((chunk_text, f"{episode_id}:{chunk_idx}"))

        logger.debug(
            "Split episode {} into {} chunks (size={}, overlap={})",
            episode_id,
            len(chunks),
            self.chunk_size,
            self.chunk_overlap,
        )

        return chunks

    def _split_transcript_by_plan(
        self,
        transcript: str,
        plan: list[EpisodePlanSegment],
    ) -> list[Episode]:
        """Split transcript into episodes based on LLM plan."""
        episodes: list[Episode] = []
        last_end = 0

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

        # Fallback: if no episodes, create one from full transcript
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
        """Get collection name for user."""
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

    def _chunk_metadata(self, chunk: EpisodeChunk) -> dict[str, Any]:
        """Prepare chunk metadata for indexing."""
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

        # Extract primary project for filtering
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
        """Normalize project alias for consistent matching."""
        cleaned = re.sub(r"[^a-z0-9]+", "_", alias.lower())
        return cleaned.strip("_")

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

            # Generate summary if not present
            if not episode.summary:
                summary_prompt = textwrap.dedent(
                    f"""
                    Summarize this meeting episode in 2-3 sentences.
                    Focus on: key decisions, action items, requirements discussed, and owners/deadlines if mentioned.

                    Episode:
                    {episode.text[:2000]}
                    """
                )
                episode.summary = await self.ai_model.generate_text(summary_prompt, max_tokens=300) or ""

            # Split large episodes into sub-chunks
            sub_chunks = self._split_large_text_into_chunks(episode.text, episode_id)

            for sub_idx, (chunk_text, chunk_id) in enumerate(sub_chunks):
                chunk = EpisodeChunk(
                    chunk_id=chunk_id,
                    text=chunk_text,
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
                        "sub_chunk_index": sub_idx,
                        "total_sub_chunks": len(sub_chunks),
                    },
                )
                indexed_chunks.append(chunk)

            # Update project tracker
            self.storage.upsert_projects(user_id, episode.project_affinity)

        self.index_chunks(user_id, indexed_chunks)
        logger.info("Successfully ingested meeting {}: {} episodes, {} chunks", meeting_id, len(episodes), len(indexed_chunks))
        return episodes