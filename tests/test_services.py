"""Tests for services module."""

from unittest.mock import AsyncMock, mock_open, patch

import pytest

from telegram_bot.file_service import FileService


class TestFileService:
    """Test the FileService class."""

    @pytest.mark.asyncio
    async def test_save_temp_file(self):
        """Test saving content to a temporary file."""
        content = b"test content"
        extension = ".txt"

        with patch("telegram_bot.file_service.get_settings") as mock_settings:
            mock_settings.return_value.temp_dir = "/tmp"

            with patch("tempfile.NamedTemporaryFile") as mock_temp:
                mock_file = mock_open()
                mock_temp.return_value.__enter__.return_value = mock_file.return_value
                mock_temp.return_value.__enter__.return_value.name = "/tmp/test.txt"

                with patch("os.makedirs"):
                    result = await FileService.save_temp_file(content, extension)

                assert result == "/tmp/test.txt"
                mock_file.return_value.write.assert_called_once_with(content)

    @pytest.mark.asyncio
    async def test_create_text_file(self):
        """Test creating a text file."""
        content = "test content"
        filename = "test.txt"

        with patch("telegram_bot.file_service.get_settings") as mock_settings:
            mock_settings.return_value.temp_dir = "/tmp"

            # Create a proper async context manager mock
            mock_file = AsyncMock()
            mock_context = AsyncMock()
            mock_context.__aenter__ = AsyncMock(return_value=mock_file)
            mock_context.__aexit__ = AsyncMock(return_value=None)

            with patch("aiofiles.open", return_value=mock_context):
                with patch("os.makedirs"):
                    with patch("os.path.join", return_value="/tmp/test.txt"):
                        result = await FileService.create_text_file(content, filename)

                assert result == "/tmp/test.txt"
                mock_file.write.assert_called_once_with(content)

    def test_cleanup_file_exists(self):
        """Test cleanup of existing file."""
        file_path = "/tmp/test.txt"

        with patch("os.path.exists", return_value=True):
            with patch("os.remove") as mock_remove:
                FileService.cleanup_file(file_path)
                mock_remove.assert_called_once_with(file_path)

    def test_cleanup_file_not_exists(self):
        """Test cleanup when file doesn't exist."""
        file_path = "/tmp/nonexistent.txt"

        with patch("os.path.exists", return_value=False):
            with patch("os.remove") as mock_remove:
                FileService.cleanup_file(file_path)
                mock_remove.assert_not_called()

    def test_cleanup_file_os_error(self):
        """Test cleanup handles OS errors gracefully."""
        file_path = "/tmp/test.txt"

        with patch("os.path.exists", return_value=True):
            with patch("os.remove", side_effect=OSError("Permission denied")):
                # Should not raise exception
                FileService.cleanup_file(file_path)
