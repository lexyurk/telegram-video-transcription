# RAG Indexing PRD

## Overview
- Integrate Retrieval-Augmented Generation (RAG) on top of meeting transcription pipeline when a user opts in.
- Support Telegram-first interaction: toggling indexing, asking free-form questions, and receiving summarized answers with citations.
- Provide scalable chunking, project attribution, and metadata storage to power project/date/topic-aware retrieval.

## Goals & Non-Goals
- **Goals**: Episode-aware chunking, per-user opt-in indexing, project/date aware retrieval, free-text query parsing, Telegram command surface, data deletion/exports.
- **Non-Goals**: UI outside Telegram, cross-user search, enterprise access control, fully automated project catalog creation.

## Data Model
- `meetings`: `meeting_id`, `user_id`, `project_id` (nullable), `scheduled_start`, `timezone`, `participants`.
- `projects`: `project_id`, `user_id`, `display_name`, `aliases[]`, `created_at`, `updated_at`.
- `episodes`: `episode_id`, `meeting_id`, `sequence_number`, `start_ts`, `end_ts`, `summary`, `topics[]`.
- `chunks`: `chunk_id`, `episode_id`, `vector`, `text`, `speaker_spans`, `project_affinity{project_id: score}`, `created_at`.
- Namespace vector storage per `user_id`; payload mirrors `chunks` metadata for filtering.

## Chunking & Project Attribution
- Split transcript into speaker turns, embed each turn, detect topic change via cosine drift + silence/turn boundaries.
- Merge contiguous turns into “episodes” with configurable overlap; store summaries and topics per episode.
- Maintain rolling project focus that decays without explicit mentions; propagate high-confidence project IDs across episodes.
- For each episode, prompt LLM for JSON with candidate projects, confidence, and supporting quotes; map aliases → project IDs.
- Record `project_affinity` scores on chunks; label highest score as primary project but persist multi-project associations.

## Parsing & Query Flow
- Treat any non-command Telegram message as potential query.
- Run dedicated LLM prompt to parse free text into JSON: `intent`, `projects[]` (with confidence), `date_ranges`, `topics`, `follow_up`, `confidence`, `uncertainty_reason`.
- Validate JSON; on failure or low confidence, store diagnostic and default to unfiltered semantic retrieval.
- Persist last successful parse per user; allow prompt to reuse prior context when new message references it implicitly.

## Retrieval & Answer Generation
- Build vector query with filtered candidates:
  - If parse returns confident projects, filter by `project_affinity.score >= threshold` (default 0.6).
  - If parse returns dates, constrain by `meeting_date` range.
  - Else, run top-K search across namespace and rerank by recency.
- Fetch supporting summaries/action items for answer scaffolding.
- Compose LLM prompt including user question, structured parse metadata, retrieved context, and citation metadata (meeting date, participants).
- Reply with concise summary, bullet list of key points, and explicit citations.
- If ambiguity detected, include quick replies (Telegram inline buttons) suggesting disambiguation options.

## Telegram Commands & State
- Supported commands: `/indexing on`, `/indexing off`, `/indexing status`, `/indexing purge`, `/list projects`.
- Store per-user state: indexing enabled flag, last parse context, project catalog edits, embedding namespace ID.
- `/indexing purge` performs confirmation (inline button) before deletion of vector records and metadata.

## Ingestion Pipeline
1. On meeting completion, check user opt-in.
2. Perform diarization cleanup, sentence segmentation, embedding for turns.
3. Detect episodes, summarize them, and tag topics via LLM.
4. Run project attribution prompt, update project catalog if new alias detected (requires user confirmation path).
5. Write chunks + metadata to vector DB; persist episodes/chunks to relational store.
6. Log attribution confidence metrics and ingestion latency.
7. Allow scheduled re-attribution job when aliases/projects change.

## Telemetry & Evaluation
- Capture raw question, structured parse, applied filters, retrieved chunk IDs, and response metadata for offline analysis.
- Build regression suite of representative queries (project-focused, date-focused, ambiguous) to monitor retrieval accuracy and prompt stability.
- Alert on sustained low parser confidence or high ambiguity rates.

## Privacy & Lifecycle
- Honor `/indexing off`: stop new ingestion but retain existing data.
- `/indexing purge`: delete vector embeddings, relational metadata, and cached context for that user.
- Provide export endpoint for user to download their indexed meeting data.
- Rotate embeddings or anonymize participants on request; log audit trail for data operations.

## Open Questions / Next Steps
- Select vector DB (Qdrant vs. Pinecone vs. self-hosted) and embedding model (OpenAI vs. local) based on latency/cost and privacy.
- Prototype episode segmentation & project attribution on sample transcripts; tune thresholds/confidence decay.
- Draft LLM prompts for parsing, attribution, and answer synthesis; collect examples for prompt testing.
- Implement Telegram bot handlers for commands and free-form queries; add inline clarification UX.
- Define monitoring dashboards for ingestion backlog, parser confidence, and retrieval latency.

