"""MTProto downloader for large files using Telethon."""

import asyncio
import os
import tempfile
import time
from typing import Optional
from pathlib import Path

import aiofiles
from loguru import logger
from telethon import TelegramClient
from telethon.tl.types import Document, DocumentAttributeFilename

from telegram_bot.config import get_settings


class DownloadStalledError(TimeoutError):
    """Raised when a Telegram file download stops making progress."""


class MTProtoDownloader:
    """Service for downloading large files using MTProto via Telethon."""

    def __init__(self) -> None:
        """Initialize the MTProto downloader."""
        self.settings = get_settings()
        self.client: Optional[TelegramClient] = None

    async def initialize(self) -> None:
        """Initialize the Telethon client."""
        try:
            self.client = TelegramClient(
                'bot_session',
                self.settings.api_id,
                self.settings.api_hash
            )
            
            # Start the client and authorize as bot
            await self.client.start(bot_token=self.settings.telegram_bot_token)
            logger.info("MTProto client initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize MTProto client: {e}")
            raise

    async def close(self) -> None:
        """Close the Telethon client."""
        if self.client:
            await self.client.disconnect()
            logger.info("MTProto client disconnected")

    async def can_download_large_file(self, file_size_mb: float) -> bool:
        """Check if we can download a large file via MTProto."""
        # Telegram's actual file size limit is 2GB
        return file_size_mb <= 2048

    async def _download_media_with_watchdog(
        self,
        message,
        temp_file_path: str,
        progress_callback=None,
    ) -> None:
        """Download media and cancel it if byte progress stalls."""
        stall_timeout = max(1, self.settings.download_stall_timeout_seconds)
        watchdog_interval = max(
            1,
            min(self.settings.download_watchdog_interval_seconds, stall_timeout),
        )
        last_progress_at = time.monotonic()
        last_progress_bytes = 0

        async def progress_hook(current: int, total: int):
            nonlocal last_progress_at, last_progress_bytes
            if current > last_progress_bytes:
                last_progress_at = time.monotonic()
                last_progress_bytes = current
            if progress_callback:
                await progress_callback(current, total)

        download_task = asyncio.create_task(
            self.client.download_media(
                message,
                file=temp_file_path,
                progress_callback=progress_hook,
            )
        )

        async def watchdog() -> None:
            while not download_task.done():
                await asyncio.sleep(watchdog_interval)
                idle_seconds = time.monotonic() - last_progress_at
                if idle_seconds >= stall_timeout:
                    download_task.cancel()
                    raise DownloadStalledError(
                        f"Download stalled for {idle_seconds:.0f}s at "
                        f"{last_progress_bytes} bytes"
                    )

        watchdog_task = asyncio.create_task(watchdog())

        done, pending = await asyncio.wait(
            {download_task, watchdog_task},
            return_when=asyncio.FIRST_COMPLETED,
        )

        for task in pending:
            task.cancel()
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)

        if watchdog_task in done:
            # Propagate DownloadStalledError if the watchdog stopped the download.
            await watchdog_task

        await download_task

    async def download_large_file(
        self,
        file_id: str,
        file_size: int,
        file_name: str,
        progress_callback=None
    ) -> Optional[str]:
        """
        Download a large file using MTProto.
        
        Args:
            file_id: Telegram file ID
            file_size: File size in bytes
            file_name: Original file name
            progress_callback: Optional callback for progress updates
            
        Returns:
            Path to downloaded file or None if failed
        """
        if not self.client:
            logger.error("MTProto client not initialized")
            return None

        try:
            # Create temp directory
            temp_dir = Path(self.settings.temp_dir)
            temp_dir.mkdir(exist_ok=True)
            
            # Generate temp file path
            file_extension = Path(file_name).suffix
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=file_extension,
                dir=temp_dir
            )
            temp_file_path = temp_file.name
            temp_file.close()

            logger.info(f"Starting MTProto download: {file_name} ({file_size / (1024*1024):.1f}MB)")

            # Get the file from Telegram
            # We need to get the actual document object from the message
            # This is a simplified approach - in practice you'd need to get the message first
            
            # Download with progress tracking
            downloaded_bytes = 0
            
            async def progress_hook(current: int, total: int):
                nonlocal downloaded_bytes
                downloaded_bytes = current
                if progress_callback:
                    await progress_callback(current, total)

            # Note: This is a simplified version. In practice, you'd need to:
            # 1. Get the message containing the file
            # 2. Extract the document from the message
            # 3. Then download it
            
            # For now, let's implement a basic version that works with the file_id
            # In a real implementation, you'd need to store message info when receiving files
            
            logger.error("MTProto download method not implemented for this file type")
            return None
            
        except Exception as e:
            logger.error(f"Error downloading large file via MTProto: {e}")
            if os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return None

    async def download_file_by_message(
        self,
        chat_id: int,
        message_id: int,
        progress_callback=None
    ) -> Optional[str]:
        """
        Download file from a specific message using MTProto.
        
        Args:
            chat_id: Chat ID where the message is
            message_id: Message ID containing the file
            progress_callback: Optional callback for progress updates
            
        Returns:
            Path to downloaded file or None if failed
        """
        if not self.client:
            logger.error("MTProto client not initialized")
            return None

        try:
            # Get the message
            message = await self.client.get_messages(chat_id, ids=message_id)
            
            if not message or not message.document:
                logger.error("Message not found or doesn't contain a document")
                return None

            document = message.document
            file_size = document.size
            
            # Get file name
            file_name = "unknown_file"
            for attr in document.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    file_name = attr.file_name
                    break

            # Create temp directory
            temp_dir = Path(self.settings.temp_dir)
            temp_dir.mkdir(exist_ok=True)
            
            # Generate temp file path
            file_extension = Path(file_name).suffix
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix=file_extension,
                dir=temp_dir
            )
            temp_file_path = temp_file.name
            temp_file.close()

            logger.info(f"Starting MTProto download: {file_name} ({file_size / (1024*1024):.1f}MB)")

            await self._download_media_with_watchdog(
                message,
                temp_file_path,
                progress_callback,
            )

            logger.info(f"Successfully downloaded large file: {temp_file_path}")
            return temp_file_path

        except DownloadStalledError as e:
            logger.error(f"Download stalled via MTProto: {e}")
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return None
        except Exception as e:
            logger.error(f"Error downloading file via MTProto: {e}")
            if 'temp_file_path' in locals() and os.path.exists(temp_file_path):
                os.remove(temp_file_path)
            return None

    async def get_file_info(self, chat_id: int, message_id: int) -> Optional[dict]:
        """
        Get file information from a message.
        
        Args:
            chat_id: Chat ID where the message is
            message_id: Message ID containing the file
            
        Returns:
            Dict with file info or None if failed
        """
        if not self.client:
            logger.error("MTProto client not initialized")
            return None

        try:
            message = await self.client.get_messages(chat_id, ids=message_id)
            
            if not message or not message.document:
                return None

            document = message.document
            
            # Get file name
            file_name = "unknown_file"
            for attr in document.attributes:
                if isinstance(attr, DocumentAttributeFilename):
                    file_name = attr.file_name
                    break

            return {
                'file_name': file_name,
                'file_size': document.size,
                'mime_type': document.mime_type,
                'file_id': str(document.id)
            }

        except Exception as e:
            logger.error(f"Error getting file info via MTProto: {e}")
            return None 
