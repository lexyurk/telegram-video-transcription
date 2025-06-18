"""Main entry point for the Telegram transcription bot."""

import asyncio
import os
import sys

from loguru import logger

from telegram_bot.bot import TelegramTranscriptionBot
from telegram_bot.config import get_settings


def setup_logging() -> None:
    """Configure logging with loguru."""
    settings = get_settings()
    # Remove default handler
    logger.remove()

    # Add console handler with custom format
    logger.add(
        sys.stdout,
        level=settings.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True,
    )

    # Add file handler for errors
    log_dir = os.path.join(settings.temp_dir, "logs")
    os.makedirs(log_dir, exist_ok=True)

    logger.add(
        os.path.join(log_dir, "bot.log"),
        level="INFO",
        rotation="1 day",
        retention="7 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )

    logger.add(
        os.path.join(log_dir, "errors.log"),
        level="ERROR",
        rotation="1 day",
        retention="30 days",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
    )


async def main() -> None:
    """Main function to run the bot."""
    try:
        # Setup logging
        setup_logging()

        # Create temp directory
        settings = get_settings()
        os.makedirs(settings.temp_dir, exist_ok=True)

        logger.info("Telegram Video Transcription Bot starting...")
        logger.info(f"Max file size: {settings.max_file_size_mb}MB")
        logger.info(f"Temp directory: {settings.temp_dir}")
        logger.info(f"Log level: {settings.log_level}")

        # Initialize and run bot
        bot = TelegramTranscriptionBot()
        await bot.run()

    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
