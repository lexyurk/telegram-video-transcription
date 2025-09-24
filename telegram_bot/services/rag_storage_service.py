"""Storage layer for RAG indexing preferences and metadata."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

from loguru import logger

from telegram_bot.config import get_settings
from telegram_bot.services.rag_intent_parser import ParsedIntent


class RAGStorageService:
    """Persist RAG-related state (indexing preferences, projects, meetings)."""

    def __init__(self, db_path: Optional[str] = None) -> None:
        settings = get_settings()
        self.db_path = Path(db_path or settings.rag_db_path)
        self.default_enabled = bool(settings.rag_enable_default)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_schema()
        self._last_intent: dict[int, dict] = {}
        logger.info("RAG storage initialized at {}", self.db_path)

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS rag_user_settings (
                    user_id INTEGER,
                    chat_id INTEGER,
                    indexing_enabled INTEGER DEFAULT 0,
                    updated_at TEXT,
                    PRIMARY KEY (user_id, chat_id)
                );

                CREATE TABLE IF NOT EXISTS rag_projects (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    alias TEXT,
                    confidence REAL,
                    occurrences INTEGER DEFAULT 1,
                    last_seen_at TEXT,
                    UNIQUE(user_id, alias)
                );

                CREATE TABLE IF NOT EXISTS rag_meetings (
                    meeting_id TEXT PRIMARY KEY,
                    user_id INTEGER,
                    chat_id INTEGER,
                    meeting_date TEXT,
                    title TEXT,
                    topics TEXT,
                    metadata TEXT
                );
                """
            )

    def is_indexing_enabled(self, user_id: int, chat_id: int) -> bool:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT indexing_enabled FROM rag_user_settings WHERE user_id=? AND chat_id=?",
                (user_id, chat_id),
            )
            row = cur.fetchone()
            if row is not None:
                return bool(row[0])
        return self.default_enabled

    def set_indexing_enabled(self, user_id: int, chat_id: int, enabled: bool) -> None:
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            conn.execute(
                """
                INSERT INTO rag_user_settings(user_id, chat_id, indexing_enabled, updated_at)
                VALUES(?, ?, ?, ?)
                ON CONFLICT(user_id, chat_id)
                DO UPDATE SET indexing_enabled=excluded.indexing_enabled, updated_at=excluded.updated_at
                """,
                (user_id, chat_id, int(enabled), now),
            )
        logger.info("Set indexing for user {} chat {} to {}", user_id, chat_id, enabled)

    def purge_user(self, user_id: int, chat_id: Optional[int] = None) -> None:
        with self._connect() as conn:
            if chat_id is not None:
                conn.execute(
                    "DELETE FROM rag_user_settings WHERE user_id=? AND chat_id=?",
                    (user_id, chat_id),
                )
                conn.execute(
                    "DELETE FROM rag_meetings WHERE user_id=? AND chat_id=?",
                    (user_id, chat_id),
                )
            else:
                conn.execute("DELETE FROM rag_user_settings WHERE user_id=?", (user_id,))
                conn.execute("DELETE FROM rag_meetings WHERE user_id=?", (user_id,))
            conn.execute("DELETE FROM rag_projects WHERE user_id=?", (user_id,))
        self._last_intent.pop(user_id, None)
        logger.info("Purged RAG data for user {}", user_id)

    def record_meeting(
        self,
        meeting_id: str,
        user_id: int,
        chat_id: int,
        meeting_date: str,
        title: str,
        topics: List[str],
        metadata: Dict[str, str],
    ) -> None:
        with self._connect() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO rag_meetings(meeting_id, user_id, chat_id, meeting_date, title, topics, metadata)
                VALUES(?, ?, ?, ?, ?, ?, ?)
                """,
                (meeting_id, user_id, chat_id, meeting_date, title, json.dumps(topics), json.dumps(metadata)),
            )
        logger.debug("Recorded meeting {} for user {}", meeting_id, user_id)

    def upsert_projects(self, user_id: int, projects: Dict[str, float]) -> None:
        if not projects:
            return
        now = datetime.utcnow().isoformat()
        with self._connect() as conn:
            for alias, confidence in projects.items():
                alias_norm = alias.strip().lower()
                if not alias_norm:
                    continue
                conn.execute(
                    """
                    INSERT INTO rag_projects(user_id, alias, confidence, occurrences, last_seen_at)
                    VALUES(?, ?, ?, 1, ?)
                    ON CONFLICT(user_id, alias)
                    DO UPDATE SET
                        confidence = excluded.confidence,
                        occurrences = rag_projects.occurrences + 1,
                        last_seen_at = excluded.last_seen_at
                    """,
                    (user_id, alias_norm, float(confidence), now),
                )
        logger.debug("Upserted projects for user {}: {}", user_id, list(projects.keys()))

    def list_projects(self, user_id: int) -> List[Dict[str, str]]:
        with self._connect() as conn:
            cur = conn.execute(
                "SELECT alias, confidence, occurrences, last_seen_at FROM rag_projects WHERE user_id=? ORDER BY alias",
                (user_id,),
            )
            rows = cur.fetchall()
        return [dict(row) for row in rows]

    def set_last_intent(self, user_id: int, intent: ParsedIntent) -> None:
        self._last_intent[user_id] = asdict(intent)

    def get_last_intent(self, user_id: int) -> Optional[dict]:
        return self._last_intent.get(user_id)

