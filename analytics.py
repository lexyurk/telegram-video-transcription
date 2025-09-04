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


def tg_distinct_id(telegram_user_id: int | str) -> str:
    return f"tg:{telegram_user_id}"


def zoom_distinct_id(zoom_user_id: str) -> str:
    return f"zoom:{zoom_user_id}"


class Analytics:
    def __init__(self, api_key: Optional[str], host: Optional[str]) -> None:
        self.enabled = bool(api_key and api_key.strip() and _PosthogClient is not None)
        self._client: Optional[_PosthogClient] = None
        if self.enabled:
            try:
                # Default to PostHog Cloud host if not provided
                resolved_host = (host or os.getenv("POSTHOG_HOST") or "https://app.posthog.com").strip()
                self._client = _PosthogClient(api_key.strip(), host=resolved_host, gzip=True)  # type: ignore[call-arg]
                atexit.register(self.flush)
            except Exception:
                # Disable analytics if initialization fails
                self.enabled = False
                self._client = None

    def identify(self, distinct_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled or not self._client:
            return
        try:
            self._client.identify(distinct_id, properties or {})
        except Exception:
            pass

    def capture(self, distinct_id: str, event: str, properties: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled or not self._client:
            return
        try:
            self._client.capture(distinct_id, event, properties or {})
        except Exception:
            pass

    def alias(self, primary_distinct_id: str, secondary_distinct_id: str) -> None:
        """
        Merge identities so both IDs represent the same user.
        """
        if not self.enabled or not self._client:
            return
        try:
            # PostHog's alias links two IDs. Order isn't critical for merging,
            # we pass both explicitly for clarity.
            self._client.alias(primary_distinct_id, secondary_distinct_id)
        except Exception:
            pass

    def flush(self) -> None:
        if not self.enabled or not self._client:
            return
        try:
            self._client.flush()
        except Exception:
            pass


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
