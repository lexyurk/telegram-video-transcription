"""Services module - imports all service classes for backward compatibility."""

# Import all services from their respective files
from telegram_bot.transcription_service import TranscriptionService
from telegram_bot.summarization_service import SummarizationService
from telegram_bot.file_service import FileService
from telegram_bot.speaker_identification_service import SpeakerIdentificationService

# Re-export all services for backward compatibility
__all__ = ["TranscriptionService", "SummarizationService", "FileService", "SpeakerIdentificationService"]
