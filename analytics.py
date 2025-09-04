"""Shared PostHog analytics helper.

Provides a tiny wrapper that is safe to import in any part of the app.
If POSTHOG_API_KEY is missing, all calls are no-ops.
"""
from __future__ import annotations

import atexit
import os
from typing import Any, Dict, Optional
from posthog import Posthog as _PosthogClient


def tg_distinct_id(telegram_user_id: int | str) -> str:
    return f"tg:{telegram_user_id}"


def zoom_distinct_id(zoom_user_id: str) -> str:
    return f"zoom:{zoom_user_id}"


class Analytics:
    def __init__(self, api_key: Optional[str], host: Optional[str]) -> None:
        # Enable when API key is present. Use official PostHog client with explicit kwargs.
        self.api_key = (api_key or "").strip()
        self.host = (host or os.getenv("POSTHOG_HOST") or "https://app.posthog.com").strip()
        self.enabled = bool(self.api_key)
        self._client: Optional[_PosthogClient] = None

        if not self.enabled:
            return

        # Instantiate client using keyword args for compatibility with v6+
        self._client = _PosthogClient(project_api_key=self.api_key, host=self.host)
        atexit.register(self.flush)

    def identify(self, distinct_id: str, properties: Optional[Dict[str, Any]] = None) -> None:
        if not self.enabled or not self._client:
            return
        try:
            # v6+ signature supports keyword args
            self._client.identify(distinct_id=distinct_id, properties=properties or {})
        except Exception:
            pass

    def capture(
        self,
        distinct_id: str,
        event: str,
        properties: Optional[Dict[str, Any]] = None,
        groups: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled or not self._client:
            return
        try:
            # v6+ signature supports keyword args
            self._client.capture(
                event=event,
                distinct_id=distinct_id,
                properties=properties or {},
                groups=groups or None,
            )
        except Exception:
            pass

    def alias(self, primary_distinct_id: str, secondary_distinct_id: str) -> None:
        """
        Merge identities so both IDs represent the same user.
        """
        if not self.enabled or not self._client:
            return
        try:
            # Use capture-based alias to be stable across client versions
            self._client.capture(
                event="$create_alias",
                distinct_id=primary_distinct_id,
                properties={"alias": secondary_distinct_id, "distinct_id": primary_distinct_id},
            )
        except Exception:
            pass

    def group_identify(
        self,
        group_type: str,
        group_key: str,
        properties: Optional[Dict[str, Any]] = None,
    ) -> None:
        if not self.enabled or not self._client:
            return
        try:
            if hasattr(self._client, "group_identify"):
                # Newer client API
                self._client.group_identify(
                    group_type=group_type, group_key=group_key, properties=properties or {}
                )
            else:
                # Fallback using capture semantics
                self._client.capture(
                    event="$groupidentify",
                    distinct_id=f"group::{group_type}:{group_key}",
                    properties={
                        "$group_type": group_type,
                        "$group_key": group_key,
                        "$group_set": properties or {},
                    },
                )
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
