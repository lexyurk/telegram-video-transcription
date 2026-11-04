"""Public service exports, loaded on demand without optional heavy dependencies."""

from importlib import import_module
from typing import Any

_SERVICE_MODULES = {
    "FileService": "file_service",
    "TranscriptionService": "transcription_service",
    "SummarizationService": "summarization_service",
    "SpeakerIdentificationService": "speaker_identification_service",
    "DiagramService": "diagram_service",
    "QuestionAnsweringService": "question_answering_service",
    "MediaInfoService": "media_info_service",
    "RAGIndexingService": "rag_indexing_service",
    "RAGQueryService": "rag_query_service",
    "RAGIntentParser": "rag_intent_parser",
    "ParsedIntent": "rag_intent_parser",
    "RAGStorageService": "rag_storage_service",
}

__all__ = list(_SERVICE_MODULES)


def __getattr__(name: str) -> Any:
    """Preserve public imports without loading unused RAG/plotting stacks."""
    module_name = _SERVICE_MODULES.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = getattr(import_module(f".{module_name}", __name__), name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
