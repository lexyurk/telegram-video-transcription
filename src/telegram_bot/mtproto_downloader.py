"""MTProto downloader for large files using Telethon."""

import asyncio
import os
import tempfile
from typing import Optional
from pathlib import Path

import aiofiles
from loguru import logger
from telethon import TelegramClient
from telethon.tl.types import Document, DocumentAttributeFilename

from .config import get_settings


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
            
            logger.warning("MTProto download not fully implemented - falling back to Bot API")
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

            # Progress tracking
            async def progress_hook(current: int, total: int):
                if progress_callback:
                    await progress_callback(current, total)

            # Download the file
            await self.client.download_media(
                message,
                file=temp_file_path,
                progress_callback=progress_hook
            )

            logger.info(f"Successfully downloaded large file: {temp_file_path}")
            return temp_file_path

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