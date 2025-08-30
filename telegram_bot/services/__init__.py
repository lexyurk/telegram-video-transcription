"""Services package for telegram bot.

This package exposes multiple service modules. To keep imports lightweight and
avoid importing heavy optional dependencies at package import time, we do not
eagerly import submodules here. Import the needed service directly, e.g.:

    from telegram_bot.services.ai_model import GeminiModel
    from telegram_bot.services.speaker_identification_service import SpeakerIdentificationService
"""

__all__: list[str] = []