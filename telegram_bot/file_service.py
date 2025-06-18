"""File service for handling file operations."""

import os
import tempfile

import aiofiles
from loguru import logger

from telegram_bot.config import get_settings


class FileService:
    """Service for handling file operations."""

    @staticmethod
    async def save_temp_file(file_content: bytes, file_extension: str) -> str:
        """
        Save content to a temporary file.

        Args:
            file_content: The file content as bytes
            file_extension: File extension (e.g., '.mp4', '.mp3')

        Returns:
            Path to the temporary file
        """
        # Create temp directory if it doesn't exist
        settings = get_settings()
        os.makedirs(settings.temp_dir, exist_ok=True)

        # Create temporary file
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=file_extension, dir=settings.temp_dir
        ) as temp_file:
            temp_file.write(file_content)
            temp_path = temp_file.name

        logger.info(f"Saved temporary file: {temp_path}")
        return temp_path

    @staticmethod
    async def create_text_file(content: str, filename: str) -> str:
        """
        Create a text file with the given content.

        Args:
            content: Text content to write
            filename: Name of the file

        Returns:
            Path to the created file
        """
        # Create temp directory if it doesn't exist
        settings = get_settings()
        os.makedirs(settings.temp_dir, exist_ok=True)

        file_path = os.path.join(settings.temp_dir, filename)

        async with aiofiles.open(file_path, "w", encoding="utf-8") as f:
            await f.write(content)

        logger.info(f"Created text file: {file_path}")
        return file_path

    @staticmethod
    def cleanup_file(file_path: str) -> None:
        """
        Remove a temporary file.

        Args:
            file_path: Path to the file to remove
        """
        try:
            if os.path.exists(file_path):
                os.remove(file_path)
                logger.info(f"Cleaned up file: {file_path}")
        except OSError as e:
            logger.warning(f"Failed to cleanup file {file_path}: {e}") 