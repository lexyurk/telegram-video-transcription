import sqlite3
import os
from contextlib import contextmanager
from typing import Optional, Any, Dict


def ensure_db(path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with sqlite3.connect(path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_user_id INTEGER,
                chat_id INTEGER,
                locale TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS zoom_connections (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER,
                zoom_user_id TEXT UNIQUE,
                access_token TEXT,
                refresh_token TEXT,
                expires_at INTEGER,
                email TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS meetings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                zoom_meeting_uuid TEXT,
                topic TEXT,
                start_time TEXT,
                owner_zoom_user_id TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS recordings (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                meeting_id INTEGER,
                file_id TEXT,
                file_type TEXT,
                download_url TEXT,
                status TEXT,
                UNIQUE(meeting_id, file_id),
                FOREIGN KEY(meeting_id) REFERENCES meetings(id)
            )
            """
        )


@contextmanager
def get_conn(path: str):
    conn = sqlite3.connect(path)
    try:
        conn.row_factory = sqlite3.Row
        yield conn
        conn.commit()
    finally:
        conn.close()


def upsert_user(conn: sqlite3.Connection, telegram_user_id: int, chat_id: int) -> int:
    cur = conn.execute(
        "SELECT id FROM users WHERE telegram_user_id = ? AND chat_id = ?",
        (telegram_user_id, chat_id),
    )
    row = cur.fetchone()
    if row:
        return int(row[0])
    cur = conn.execute(
        "INSERT INTO users(telegram_user_id, chat_id) VALUES(?, ?)",
        (telegram_user_id, chat_id),
    )
    return int(cur.lastrowid)


def save_connection(
    conn: sqlite3.Connection,
    zoom_user_id: str,
    user_id: int,
    tokens: Dict[str, Any],
    email: Optional[str] = None,
) -> None:
    expires_in = int(tokens.get("expires_in", 3600))
    from time import time

    expires_at = int(time()) + expires_in - 60
    conn.execute(
        """
        INSERT INTO zoom_connections(zoom_user_id, user_id, access_token, refresh_token, expires_at, email)
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(zoom_user_id) DO UPDATE SET
          user_id=excluded.user_id,
          access_token=excluded.access_token,
          refresh_token=excluded.refresh_token,
          expires_at=excluded.expires_at,
          email=excluded.email
        """,
        (
            zoom_user_id,
            user_id,
            tokens.get("access_token"),
            tokens.get("refresh_token"),
            expires_at,
            email,
        ),
    )


def get_connection_by_zoom_user_id(conn: sqlite3.Connection, zoom_user_id: str) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        "SELECT * FROM zoom_connections WHERE zoom_user_id = ?",
        (zoom_user_id,),
    )
    return cur.fetchone()


def get_chat_id_for_zoom_user(conn: sqlite3.Connection, zoom_user_id: str) -> Optional[int]:
    cur = conn.execute(
        """
        SELECT users.chat_id FROM zoom_connections
        JOIN users ON users.id = zoom_connections.user_id
        WHERE zoom_connections.zoom_user_id = ?
        """,
        (zoom_user_id,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else None


def delete_connection(conn: sqlite3.Connection, zoom_user_id: str) -> None:
    conn.execute("DELETE FROM zoom_connections WHERE zoom_user_id = ?", (zoom_user_id,))


def upsert_meeting(
    conn: sqlite3.Connection,
    zoom_meeting_uuid: str,
    topic: Optional[str],
    start_time: Optional[str],
    owner_zoom_user_id: Optional[str],
) -> int:
    cur = conn.execute(
        "SELECT id FROM meetings WHERE zoom_meeting_uuid = ?",
        (zoom_meeting_uuid,),
    )
    row = cur.fetchone()
    if row:
        meeting_id = int(row[0])
        conn.execute(
            "UPDATE meetings SET topic = ?, start_time = ?, owner_zoom_user_id = ? WHERE id = ?",
            (topic, start_time, owner_zoom_user_id, meeting_id),
        )
        return meeting_id
    cur = conn.execute(
        "INSERT INTO meetings(zoom_meeting_uuid, topic, start_time, owner_zoom_user_id) VALUES(?, ?, ?, ?)",
        (zoom_meeting_uuid, topic, start_time, owner_zoom_user_id),
    )
    return int(cur.lastrowid)


def insert_recording_if_new(
    conn: sqlite3.Connection,
    meeting_id: int,
    file_id: str,
    file_type: Optional[str],
    download_url: Optional[str],
) -> bool:
    try:
        conn.execute(
            "INSERT INTO recordings(meeting_id, file_id, file_type, download_url, status) VALUES(?, ?, ?, ?, ?)",
            (meeting_id, file_id, file_type, download_url, "queued"),
        )
        return True
    except sqlite3.IntegrityError:
        return False


def get_connection_by_telegram(
    conn: sqlite3.Connection, telegram_user_id: int, chat_id: int
) -> Optional[sqlite3.Row]:
    cur = conn.execute(
        """
        SELECT zc.* FROM zoom_connections zc
        JOIN users u ON u.id = zc.user_id
        WHERE u.telegram_user_id = ? AND u.chat_id = ?
        """,
        (telegram_user_id, chat_id),
    )
    return cur.fetchone()


def update_tokens_by_zoom_user_id(
    conn: sqlite3.Connection, zoom_user_id: str, tokens: Dict[str, Any]
) -> None:
    from time import time

    expires_in = int(tokens.get("expires_in", 3600))
    expires_at = int(time()) + expires_in - 60
    conn.execute(
        """
        UPDATE zoom_connections
        SET access_token = ?, refresh_token = ?, expires_at = ?
        WHERE zoom_user_id = ?
        """,
        (
            tokens.get("access_token"),
            tokens.get("refresh_token"),
            expires_at,
            zoom_user_id,
        ),
    )


