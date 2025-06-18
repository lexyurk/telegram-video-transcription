"""Services module - imports all service classes for backward compatibility."""

# Import all services from the services package
from telegram_bot.services.transcription_service import TranscriptionService
from telegram_bot.services.summarization_service import SummarizationService
from telegram_bot.services.file_service import FileService
from telegram_bot.services.speaker_identification_service import SpeakerIdentificationService

# Re-export all services for backward compatibility
__all__ = ["TranscriptionService", "SummarizationService", "FileService", "SpeakerIdentificationService"]
