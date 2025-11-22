"""Embedding function that uses Gemini's embedding API."""

from typing import Any, Iterable

from google import genai
from loguru import logger


class GeminiEmbeddingFunction:
    """Callable embedding function compatible with ChromaDB."""

    def __init__(self, api_key: str, model_name: str = "text-embedding-004") -> None:
        if not api_key:
            raise ValueError("GOOGLE_API_KEY is required to use Gemini embeddings.")
        self.client = genai.Client(api_key=api_key)
        self.model_name = model_name

    def __call__(self, texts: str | Iterable[str]) -> list[list[float]]:
        inputs = [texts] if isinstance(texts, str) else list(texts)
        embeddings: list[list[float]] = []

        for text in inputs:
            normalized = (text or "").strip()
            if not normalized:
                embeddings.append([])
                continue

            try:
                response = self.client.models.embed_content(
                    model=self.model_name,
                    contents=normalized,
                )
                embeddings.append(self._extract_embedding(response))
            except Exception as exc:
                logger.error("Gemini embedding request failed: {}", exc)
                embeddings.append([])

        return embeddings

    @staticmethod
    def _extract_embedding(response: Any) -> list[float]:
        """Extract embedding vector from Gemini response."""
        embedding = getattr(response, "embedding", None)
        if embedding and hasattr(embedding, "values"):
            return list(embedding.values)

        embeddings = getattr(response, "embeddings", None)
        if embeddings:
            candidate = embeddings[0]
            values = getattr(candidate, "values", None)
            if values is not None:
                return list(values)

        raise ValueError("Gemini embed response did not include embedding values.")

