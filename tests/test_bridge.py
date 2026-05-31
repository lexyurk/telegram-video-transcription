"""Tests for the bridge feature — DB migration, /bridge command, forward_to_bridge."""

import os
import sqlite3
import tempfile
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from zoom_backend.db import (
    ensure_db,
    get_conn,
    upsert_user,
    save_connection,
    set_bridge_chat_id,
    get_bridge_chat_id,
    get_connection_by_telegram_user_id,
    get_connection_by_user_id,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db() -> str:
    """Create a temporary DB and return its path."""
    fd, path = tempfile.mkstemp(suffix=".sqlite3")
    os.close(fd)
    ensure_db(path)
    return path


def _seed_connection(path: str, telegram_user_id: int = 111, chat_id: int = 222) -> str:
    """Insert a user + zoom connection and return zoom_user_id."""
    zoom_user_id = "zoom_abc123"
    with get_conn(path) as conn:
        user_id = upsert_user(conn, telegram_user_id, chat_id)
        save_connection(
            conn,
            zoom_user_id,
            user_id,
            {"access_token": "at", "refresh_token": "rt", "expires_in": 3600},
            email="user@example.com",
        )
    return zoom_user_id


# ---------------------------------------------------------------------------
# 1. DB Migration Tests
# ---------------------------------------------------------------------------

class TestBridgeMigration:
    def test_bridge_chat_id_column_exists_after_ensure_db(self):
        path = _make_db()
        try:
            with get_conn(path) as conn:
                cur = conn.execute("PRAGMA table_info(zoom_connections)")
                columns = {row["name"] for row in cur.fetchall()}
            assert "bridge_chat_id" in columns
        finally:
            os.unlink(path)

    def test_migration_is_idempotent(self):
        """Calling ensure_db twice should not fail."""
        path = _make_db()
        try:
            ensure_db(path)  # second call
            with get_conn(path) as conn:
                cur = conn.execute("PRAGMA table_info(zoom_connections)")
                columns = [row["name"] for row in cur.fetchall()]
            assert columns.count("bridge_chat_id") == 1
        finally:
            os.unlink(path)

    def test_bridge_chat_id_defaults_to_null(self):
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                result = get_bridge_chat_id(conn, zoom_user_id)
            assert result is None
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 2. DB helper function tests
# ---------------------------------------------------------------------------

class TestBridgeDbHelpers:
    def test_set_and_get_bridge_chat_id(self):
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                set_bridge_chat_id(conn, zoom_user_id, 999)
            with get_conn(path) as conn:
                assert get_bridge_chat_id(conn, zoom_user_id) == 999
        finally:
            os.unlink(path)

    def test_clear_bridge_chat_id(self):
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                set_bridge_chat_id(conn, zoom_user_id, 999)
            with get_conn(path) as conn:
                set_bridge_chat_id(conn, zoom_user_id, None)
            with get_conn(path) as conn:
                assert get_bridge_chat_id(conn, zoom_user_id) is None
        finally:
            os.unlink(path)

    def test_get_connection_by_user_id(self):
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                user_id = upsert_user(conn, 111, 222)
                row = get_connection_by_user_id(conn, user_id)
            assert row is not None
            assert row["zoom_user_id"] == zoom_user_id
        finally:
            os.unlink(path)

    def test_get_connection_by_user_id_not_found(self):
        path = _make_db()
        try:
            with get_conn(path) as conn:
                row = get_connection_by_user_id(conn, 99999)
            assert row is None
        finally:
            os.unlink(path)

    def test_get_connection_by_telegram_user_id_across_chats(self):
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path, telegram_user_id=111, chat_id=100)
            with get_conn(path) as conn:
                upsert_user(conn, 111, 200)
                row = get_connection_by_telegram_user_id(conn, 111)
            assert row is not None
            assert row["zoom_user_id"] == zoom_user_id
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 3. /bridge command tests
# ---------------------------------------------------------------------------

ENV_VARS = {
    "TELEGRAM_BOT_TOKEN": "test_token",
    "TELEGRAM_API_ID": "123456",
    "TELEGRAM_API_HASH": "test_hash",
    "DEEPGRAM_API_KEY": "test_deepgram",
    "GOOGLE_API_KEY": "test_google",
}


def _make_update(user_id: int = 111, chat_id: int = 222):
    """Build a minimal mock Update + context."""
    update = MagicMock()
    update.effective_user.id = user_id
    update.effective_chat.id = chat_id
    update.message.reply_text = AsyncMock()
    return update


def _make_context(args=None):
    ctx = MagicMock()
    ctx.args = args or []
    return ctx


class TestBridgeCommand:
    @pytest.mark.asyncio
    async def test_bridge_no_zoom_connection(self):
        path = _make_db()
        try:
            update = _make_update()
            ctx = _make_context()
            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                from telegram_bot.bot import TelegramTranscriptionBot
                bot = TelegramTranscriptionBot()
                await bot.bridge_command(update, ctx)
            update.message.reply_text.assert_awaited_once()
            text = update.message.reply_text.call_args[0][0]
            assert "No Zoom account connected" in text
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_bridge_on(self):
        path = _make_db()
        try:
            _seed_connection(path)
            update = _make_update()
            ctx = _make_context(args=["on"])
            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                from telegram_bot.bot import TelegramTranscriptionBot
                bot = TelegramTranscriptionBot()
                await bot.bridge_command(update, ctx)
            text = update.message.reply_text.call_args[0][0]
            assert "Bridge enabled" in text

            # Verify DB
            with get_conn(path) as conn:
                assert get_bridge_chat_id(conn, "zoom_abc123") == 222
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_bridge_on_uses_connection_from_different_chat(self):
        path = _make_db()
        try:
            _seed_connection(path, telegram_user_id=111, chat_id=100)
            update = _make_update(user_id=111, chat_id=200)
            ctx = _make_context(args=["on"])
            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                from telegram_bot.bot import TelegramTranscriptionBot
                bot = TelegramTranscriptionBot()
                await bot.bridge_command(update, ctx)
            text = update.message.reply_text.call_args[0][0]
            assert "No Zoom account connected" not in text
            assert "Bridge enabled" in text

            with get_conn(path) as conn:
                assert get_bridge_chat_id(conn, "zoom_abc123") == 200
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_bridge_off(self):
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                set_bridge_chat_id(conn, zoom_user_id, 222)

            update = _make_update()
            ctx = _make_context(args=["off"])
            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                from telegram_bot.bot import TelegramTranscriptionBot
                bot = TelegramTranscriptionBot()
                await bot.bridge_command(update, ctx)
            text = update.message.reply_text.call_args[0][0]
            assert "Bridge disabled" in text

            with get_conn(path) as conn:
                assert get_bridge_chat_id(conn, zoom_user_id) is None
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("args", "bridge_chat_id"),
        [
            (["on"], None),
            (["off"], 222),
            ([], 222),
            ([], None),
        ],
    )
    async def test_bridge_replies_use_legacy_markdown_bold(self, args, bridge_chat_id):
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            if bridge_chat_id is not None:
                with get_conn(path) as conn:
                    set_bridge_chat_id(conn, zoom_user_id, bridge_chat_id)

            update = _make_update()
            ctx = _make_context(args=args)
            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                from telegram_bot.bot import TelegramTranscriptionBot
                bot = TelegramTranscriptionBot()
                await bot.bridge_command(update, ctx)

            text = update.message.reply_text.call_args[0][0]
            assert "**" not in text
            assert "*" in text
            assert update.message.reply_text.call_args.kwargs["parse_mode"] == "Markdown"
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_bridge_status_on(self):
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                set_bridge_chat_id(conn, zoom_user_id, 222)

            update = _make_update()
            ctx = _make_context()
            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                from telegram_bot.bot import TelegramTranscriptionBot
                bot = TelegramTranscriptionBot()
                await bot.bridge_command(update, ctx)
            text = update.message.reply_text.call_args[0][0]
            assert "Status: ON" in text
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_bridge_status_off(self):
        path = _make_db()
        try:
            _seed_connection(path)
            update = _make_update()
            ctx = _make_context()
            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                from telegram_bot.bot import TelegramTranscriptionBot
                bot = TelegramTranscriptionBot()
                await bot.bridge_command(update, ctx)
            text = update.message.reply_text.call_args[0][0]
            assert "Status: OFF" in text
        finally:
            os.unlink(path)


# ---------------------------------------------------------------------------
# 4. forward_to_bridge() tests
# ---------------------------------------------------------------------------

class TestForwardToBridge:
    @pytest.mark.asyncio
    async def test_forward_to_bridge_skips_when_no_bridge(self):
        """When no bridge_chat_id is set, nothing should be sent."""
        path = _make_db()
        try:
            _seed_connection(path)
            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                from zoom_backend.app import forward_to_bridge, send_message
                with patch("zoom_backend.app.send_message", new_callable=AsyncMock) as mock_send:
                    await forward_to_bridge(
                        zoom_user_id="zoom_abc123",
                        topic="Test Meeting",
                        transcript_with_date="Hello world",
                        summary="Summary text",
                        recording_date="February 5, 2026 at 10:00",
                        meeting_uuid="uuid-1234-5678",
                        participants=["Alice", "Bob"],
                    )
                    mock_send.assert_not_awaited()
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_forward_to_bridge_sends_when_configured(self):
        """When bridge_chat_id is set, should send header + document + summary."""
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                set_bridge_chat_id(conn, zoom_user_id, 999)

            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                with patch("zoom_backend.app.send_message", new_callable=AsyncMock) as mock_send, \
                     patch("zoom_backend.app.send_telegram_document", new_callable=AsyncMock) as mock_doc, \
                     patch("zoom_backend.app.send_long_message", new_callable=AsyncMock) as mock_long:
                    # Mock FileService.create_text_file
                    with patch("zoom_backend.app.FileService") as MockFS:
                        mock_fs_instance = MockFS.return_value
                        mock_fs_instance.create_text_file = AsyncMock(return_value="/tmp/test.txt")

                        from zoom_backend.app import forward_to_bridge
                        await forward_to_bridge(
                            zoom_user_id="zoom_abc123",
                            topic="Sprint Planning",
                            transcript_with_date="Recording Date: Feb 5\n\nAlice: Hi\nBob: Hello",
                            summary="Key decisions were made.",
                            recording_date="February 5, 2026 at 10:00",
                            meeting_uuid="uuid-1234-5678-abcd-ef",
                            participants=["Alice", "Bob"],
                        )

                    # Header message
                    mock_send.assert_awaited_once()
                    header_text = mock_send.call_args[0][1]
                    assert "Sprint Planning" in header_text
                    assert "Alice" in header_text
                    assert mock_send.call_args[0][0] == 999

                    # Document
                    mock_doc.assert_awaited_once()
                    assert mock_doc.call_args[0][0] == 999

                    # Summary
                    mock_long.assert_awaited_once()
                    assert mock_long.call_args[0][0] == 999
                    assert "Key decisions" in mock_long.call_args[0][1]
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_forward_to_bridge_no_summary(self):
        """When summary is None, should not call send_long_message."""
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                set_bridge_chat_id(conn, zoom_user_id, 999)

            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                with patch("zoom_backend.app.send_message", new_callable=AsyncMock), \
                     patch("zoom_backend.app.send_telegram_document", new_callable=AsyncMock), \
                     patch("zoom_backend.app.send_long_message", new_callable=AsyncMock) as mock_long:
                    with patch("zoom_backend.app.FileService") as MockFS:
                        mock_fs_instance = MockFS.return_value
                        mock_fs_instance.create_text_file = AsyncMock(return_value="/tmp/test.txt")

                        from zoom_backend.app import forward_to_bridge
                        await forward_to_bridge(
                            zoom_user_id="zoom_abc123",
                            topic="Standup",
                            transcript_with_date="Hi everyone",
                            summary=None,
                            recording_date=None,
                            meeting_uuid="uuid-0000",
                            participants=[],
                        )
                    mock_long.assert_not_awaited()
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_forward_to_bridge_handles_error_gracefully(self):
        """If sending fails, forward_to_bridge should not raise."""
        path = _make_db()
        try:
            zoom_user_id = _seed_connection(path)
            with get_conn(path) as conn:
                set_bridge_chat_id(conn, zoom_user_id, 999)

            with patch.dict(os.environ, {**ENV_VARS, "ZOOM_DB_PATH": path}):
                with patch("zoom_backend.app.send_message", new_callable=AsyncMock) as mock_send:
                    mock_send.side_effect = Exception("Telegram API error")
                    from zoom_backend.app import forward_to_bridge
                    # Should not raise
                    await forward_to_bridge(
                        zoom_user_id="zoom_abc123",
                        topic="Broken",
                        transcript_with_date="text",
                        summary="sum",
                        recording_date=None,
                        meeting_uuid="uuid",
                        participants=[],
                    )
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_forward_to_bridge_handles_db_error_gracefully(self):
        """If bridge DB lookup fails, forward_to_bridge should not raise."""
        with patch("zoom_backend.app.get_settings", side_effect=sqlite3.Error("DB error")):
            from zoom_backend.app import forward_to_bridge

            await forward_to_bridge(
                zoom_user_id="zoom_abc123",
                topic="Broken",
                transcript_with_date="text",
                summary="sum",
                recording_date=None,
                meeting_uuid="uuid",
                participants=[],
            )
