"""Shared PostHog analytics helper.

Provides a tiny wrapper that is safe to import in any part of the app.
If POSTHOG_API_KEY is missing, all calls are no-ops.
"""
from __future__ import annotations

import atexit
import os
from typing import Any, Dict, Optional

try:
    # Import lazily in case dependency is not installed in some environments
    from posthog import Posthog as _PosthogClient  # type: ignore
except Exception:  # pragma: no cover - library may be missing locally
    _PosthogClient = None  # type: ignore

try:
    import httpx  # type: ignore
except Exception:  # pragma: no cover
    httpx = None  # type: ignore


def tg_distinct_id(telegram_user_id: int | str) -> str:
    return f"tg:{telegram_user_id}"


def zoom_distinct_id(zoom_user_id: str) -> str:
    return f"zoom:{zoom_user_id}"


class Analytics:
    def __init__(self, api_key: Optional[str], host: Optional[str]) -> None:
        # Enable when API key is present. Prefer official client if available; otherwise, use HTTP fallback.
        self.api_key = (api_key or "").strip()
        self.host = (host or os.getenv("POSTHOG_HOST") or "https://app.posthog.com").strip()
        self.enabled = bool(self.api_key)
        self._client: Optional[_PosthogClient] = None
        self._http_client: Optional["httpx.Client"] = None  # type: ignore[name-defined]

        if not self.enabled:
            return

        if _PosthogClient is not None:
            try:
                self._client = _PosthogClient(self.api_key, host=self.host, gzip=True)  # type: ignore[call-arg]
                atexit.register(self.flush)
            except Exception:
                self._client = None
        if self._client is None and httpx is not None:
            try:
                # Keep a small, shared HTTP client for efficiency
                self._http_client = httpx.Client(timeout=5.0)
                atexit.register(self.flush)
            except Exception:
                self._http_client = None

    def identify(self, distinct_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return
        if self._client is not None:
            try:
                self._client.identify(distinct_id, properties or {})
            except Exception:
                pass
            return
        # HTTP fallback
        if self._http_client is not None:
            try:
                payload = {
                    "api_key": self.api_key,
                    "event": "$identify",
                    "distinct_id": distinct_id,
                    "properties": {"$set": properties or {}},
                }
                self._http_client.post(self._capture_url(), json=payload)
            except Exception:
                pass

    def capture(self, distinct_id: str, event: str, properties: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled:
            return
        if self._client is not None:
            try:
                self._client.capture(distinct_id, event, properties or {})
            except Exception:
                pass
            return
        # HTTP fallback
        if self._http_client is not None:
            try:
                payload = {
                    "api_key": self.api_key,
                    "event": event,
                    "distinct_id": distinct_id,
                    "properties": properties or {},
                }
                self._http_client.post(self._capture_url(), json=payload)
            except Exception:
                pass

    def alias(self, primary_distinct_id: str, secondary_distinct_id: str) -> None:
        """
        Merge identities so both IDs represent the same user.
        """
        if not self.enabled:
            return
        if self._client is not None:
            try:
                # PostHog's alias links two IDs. Order isn't critical for merging,
                # we pass both explicitly for clarity.
                self._client.alias(primary_distinct_id, secondary_distinct_id)
            except Exception:
                pass
            return
        # HTTP fallback via $create_alias
        if self._http_client is not None:
            try:
                payload = {
                    "api_key": self.api_key,
                    "event": "$create_alias",
                    "distinct_id": primary_distinct_id,
                    "properties": {"alias": secondary_distinct_id, "distinct_id": primary_distinct_id},
                }
                self._http_client.post(self._capture_url(), json=payload)
            except Exception:
                pass

    def flush(self) -> None:
        if not self.enabled:
            return
        if self._client is not None:
            try:
                self._client.flush()
            except Exception:
                pass
        if self._http_client is not None:
            try:
                self._http_client.close()
            except Exception:
                pass

    def _capture_url(self) -> str:
        # Ensure single trailing slash
        base = self.host.rstrip("/")
        return f"{base}/capture/"


# Lazy settings import to avoid circulars at module import time
_api_key = None
_host = None
try:
    from telegram_bot.config import get_settings  # local import

    s = get_settings()
    _api_key = getattr(s, "posthog_api_key", None)
    _host = getattr(s, "posthog_host", None)
except Exception:
    # Fall back to environment variables if config isn't available yet
    _api_key = os.getenv("POSTHOG_API_KEY")
    _host = os.getenv("POSTHOG_HOST")

analytics = Analytics(_api_key, _host)
