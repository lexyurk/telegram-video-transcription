#!/usr/bin/env python3
"""Entry point for the Telegram transcription bot."""

import asyncio
from src.telegram_bot.main import main

if __name__ == "__main__":
    asyncio.run(main()) 