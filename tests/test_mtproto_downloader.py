"""Tests for MTProto download failure handling."""

import asyncio
import os
from types import SimpleNamespace
from unittest.mock import patch

from telegram_bot.mtproto_downloader import MTProtoDownloader


def _env(temp_dir: str) -> dict[str, str]:
    return {
        "TELEGRAM_BOT_TOKEN": "test_token",
        "TELEGRAM_API_ID": "123456",
        "TELEGRAM_API_HASH": "test_hash",
        "DEEPGRAM_API_KEY": "test_deepgram",
        "GOOGLE_API_KEY": "test_google",
        "TEMP_DIR": temp_dir,
        "DOWNLOAD_STALL_TIMEOUT_SECONDS": "1",
        "DOWNLOAD_WATCHDOG_INTERVAL_SECONDS": "1",
    }


def _message(size: int = 1024) -> SimpleNamespace:
    return SimpleNamespace(
        document=SimpleNamespace(
            size=size,
            attributes=[],
        )
    )


async def test_download_file_by_message_removes_partial_file_on_stall(tmp_path):
    """A stuck Telegram download should fail cleanly instead of hanging forever."""

    class StallingClient:
        async def get_messages(self, chat_id, ids):
            return _message()

        async def download_media(self, message, file, progress_callback):
            with open(file, "wb") as handle:
                handle.write(b"partial")
            await asyncio.sleep(10)

    with patch.dict(os.environ, _env(str(tmp_path)), clear=True):
        downloader = MTProtoDownloader()
        downloader.client = StallingClient()

        result = await downloader.download_file_by_message(123, 456)

    assert result is None
    assert list(tmp_path.iterdir()) == []


async def test_download_file_by_message_returns_path_when_download_completes(tmp_path):
    """A healthy Telegram download should still return the completed temp file."""

    class HealthyClient:
        async def get_messages(self, chat_id, ids):
            return _message(size=2)

        async def download_media(self, message, file, progress_callback):
            await progress_callback(1, 2)
            with open(file, "wb") as handle:
                handle.write(b"ok")
            await progress_callback(2, 2)

    with patch.dict(os.environ, _env(str(tmp_path)), clear=True):
        downloader = MTProtoDownloader()
        downloader.client = HealthyClient()

        result = await downloader.download_file_by_message(123, 456)

    assert result is not None
    assert os.path.exists(result)
    assert open(result, "rb").read() == b"ok"
