"""Analytics service using PostHog for tracking bot usage and performance."""

import os
from datetime import datetime
from typing import Dict, Optional

from loguru import logger

try:
    import posthog
except ImportError:
    posthog = None
    logger.warning("PostHog not installed. Run: pip install posthog")

from telegram_bot.config import get_settings


class AnalyticsService:
    """Service for tracking bot analytics using PostHog."""
    
    def __init__(self):
        """Initialize the analytics service."""
        self.settings = get_settings()
        self.enabled = False
        
        # Check if PostHog is available and configured
        if posthog is None:
            logger.warning("PostHog not installed. Analytics disabled.")
            return
            
        # Get PostHog configuration from environment
        self.api_key = os.getenv("POSTHOG_API_KEY")
        self.host = os.getenv("POSTHOG_HOST", "https://app.posthog.com")
        
        if not self.api_key:
            logger.warning("POSTHOG_API_KEY not set. Analytics disabled.")
            return
            
        # Initialize PostHog
        try:
            posthog.api_key = self.api_key
            posthog.host = self.host
            self.enabled = True
            logger.info("PostHog analytics enabled")
        except Exception as e:
            logger.error(f"Failed to initialize PostHog: {e}")
    
    def _get_user_id(self, telegram_user_id: int) -> str:
        """Convert Telegram user ID to analytics user ID."""
        return f"telegram_{telegram_user_id}"
    
    def _get_user_properties(self, username: Optional[str] = None, first_name: Optional[str] = None, 
                           last_name: Optional[str] = None) -> Dict:
        """Get user properties for analytics."""
        properties = {}
        
        if username:
            properties["username"] = username
        if first_name:
            properties["first_name"] = first_name
        if last_name:
            properties["last_name"] = last_name
            
        return properties
    
    async def track_user_started_bot(self, user_id: int, username: Optional[str] = None, 
                                   first_name: Optional[str] = None, last_name: Optional[str] = None) -> None:
        """Track when a user starts the bot."""
        if not self.enabled:
            return
            
        try:
            analytics_user_id = self._get_user_id(user_id)
            properties = self._get_user_properties(username, first_name, last_name)
            
            # Identify user
            posthog.identify(analytics_user_id, properties)
            
            # Track event
            posthog.capture(
                analytics_user_id,
                "Bot Started",
                properties={
                    "source": "telegram",
                    **properties
                }
            )
            
        except Exception as e:
            logger.error(f"Failed to track user started bot: {e}")
    
    async def track_help_requested(self, user_id: int) -> None:
        """Track when a user requests help."""
        if not self.enabled:
            return
            
        try:
            posthog.capture(
                self._get_user_id(user_id),
                "Help Requested",
                properties={"source": "telegram"}
            )
        except Exception as e:
            logger.error(f"Failed to track help requested: {e}")
    
    async def track_file_uploaded(self, user_id: int, file_name: str, 
                                file_size_mb: float, file_type: str) -> None:
        """Track when a user uploads a file."""
        if not self.enabled:
            return
            
        try:
            posthog.capture(
                self._get_user_id(user_id),
                "File Uploaded",
                properties={
                    "source": "telegram",
                    "file_name": file_name,
                    "file_size_mb": file_size_mb,
                    "file_type": file_type,
                    "file_extension": os.path.splitext(file_name)[1].lower()
                }
            )
        except Exception as e:
            logger.error(f"Failed to track file uploaded: {e}")
    
    async def track_transcription_started(self, user_id: int, file_name: str, 
                                        file_size_mb: float) -> None:
        """Track when transcription starts."""
        if not self.enabled:
            return
            
        try:
            posthog.capture(
                self._get_user_id(user_id),
                "Transcription Started",
                properties={
                    "source": "telegram",
                    "file_name": file_name,
                    "file_size_mb": file_size_mb
                }
            )
        except Exception as e:
            logger.error(f"Failed to track transcription started: {e}")
    
    async def track_transcription_completed(self, user_id: int, file_name: str, 
                                          file_size_mb: float, processing_time_seconds: float) -> None:
        """Track when transcription completes successfully."""
        if not self.enabled:
            return
            
        try:
            posthog.capture(
                self._get_user_id(user_id),
                "Transcription Completed",
                properties={
                    "source": "telegram",
                    "file_name": file_name,
                    "file_size_mb": file_size_mb,
                    "processing_time_seconds": processing_time_seconds,
                    "processing_speed_mb_per_second": file_size_mb / processing_time_seconds if processing_time_seconds > 0 else 0
                }
            )
        except Exception as e:
            logger.error(f"Failed to track transcription completed: {e}")
    
    async def track_transcription_failed(self, user_id: int, file_name: str, 
                                       file_size_mb: float, error_message: str) -> None:
        """Track when transcription fails."""
        if not self.enabled:
            return
            
        try:
            posthog.capture(
                self._get_user_id(user_id),
                "Transcription Failed",
                properties={
                    "source": "telegram",
                    "file_name": file_name,
                    "file_size_mb": file_size_mb,
                    "error_message": error_message
                }
            )
        except Exception as e:
            logger.error(f"Failed to track transcription failed: {e}")
    
    async def track_unsupported_file(self, user_id: int, file_name: Optional[str] = None, 
                                   message_type: Optional[str] = None) -> None:
        """Track when user sends unsupported file or message."""
        if not self.enabled:
            return
            
        try:
            posthog.capture(
                self._get_user_id(user_id),
                "Unsupported File",
                properties={
                    "source": "telegram",
                    "file_name": file_name,
                    "message_type": message_type
                }
            )
        except Exception as e:
            logger.error(f"Failed to track unsupported file: {e}")
    
    async def track_summary_generated(self, user_id: int, file_name: str) -> None:
        """Track when AI summary is generated."""
        if not self.enabled:
            return
            
        try:
            posthog.capture(
                self._get_user_id(user_id),
                "Summary Generated",
                properties={
                    "source": "telegram",
                    "file_name": file_name
                }
            )
        except Exception as e:
            logger.error(f"Failed to track summary generated: {e}")
    
    async def track_custom_event(self, user_id: int, event_name: str, 
                               properties: Optional[Dict] = None) -> None:
        """Track a custom event."""
        if not self.enabled:
            return
            
        try:
            event_properties = {"source": "telegram"}
            if properties:
                event_properties.update(properties)
                
            posthog.capture(
                self._get_user_id(user_id),
                event_name,
                properties=event_properties
            )
        except Exception as e:
            logger.error(f"Failed to track custom event {event_name}: {e}")


# Global instance
_analytics_service = None

def get_analytics_service() -> AnalyticsService:
    """Get the global analytics service instance."""
    global _analytics_service
    if _analytics_service is None:
        _analytics_service = AnalyticsService()
    return _analytics_service