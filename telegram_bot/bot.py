"""Main Telegram bot implementation with MTProto support for large files."""

import asyncio
import os
from datetime import datetime

from loguru import logger
from telegram import Document, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from telegram_bot.config import get_settings
from telegram_bot.services import (
    FileService,
    TranscriptionService, 
    SummarizationService,
    SpeakerIdentificationService,
)
from telegram_bot.mtproto_downloader import MTProtoDownloader


class TelegramTranscriptionBot:
    """Main bot class for handling Telegram interactions with large file support."""

    def __init__(self) -> None:
        """Initialize the bot with services."""
        self.transcription_service = TranscriptionService()
        self.summarization_service = SummarizationService()
        self.speaker_identification_service = SpeakerIdentificationService()
        self.file_service = FileService()
        self.mtproto_downloader = MTProtoDownloader()

    async def initialize(self) -> None:
        """Initialize the bot services."""
        await self.mtproto_downloader.initialize()
        logger.info("Bot services initialized")

    async def cleanup(self) -> None:
        """Cleanup bot services."""
        await self.mtproto_downloader.close()
        logger.info("Bot services cleaned up")

    async def start_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /start command."""
        settings = get_settings()
        
        # Determine which AI model is being used
        ai_provider = "Gemini 2.5 Flash" if settings.google_api_key else "Claude AI"
        
        welcome_message = f"""
🎥 **Video/Audio Transcription Bot** 🎙️

Welcome! I can transcribe your video and audio files and create summaries with action points using {ai_provider}.

**How it works:**
1. Send me any video or audio file (up to 2GB!)
2. I'll transcribe it and send you a .txt file
3. I'll also create a summary with key points

**Supported formats:**
• **Video:** MP4, AVI, MOV, MKV, WMV, WebM
• **Audio:** MP3, WAV, AAC, FLAC, OGG, M4A

**Commands:**
/start - Show this message
/help - Show help

Just send me a file and I'll handle the rest! 🚀
        """

        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        logger.info(f"User {update.effective_user.id} started the bot")

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /help command."""
        await self.start_command(update, context)

    async def handle_file(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle file uploads (documents, audio, video) with large file support up to 2GB."""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        message_id = update.message.message_id

        # Get file info from different message types
        file_obj = None
        file_name = None
        file_size = None
        file_id = None

        if update.message.document:
            file_obj = update.message.document
            file_name = file_obj.file_name
            file_size = file_obj.file_size
            file_id = file_obj.file_id
        elif update.message.audio:
            file_obj = update.message.audio
            file_name = file_obj.file_name or f"audio_{file_obj.file_id[:8]}.{file_obj.mime_type.split('/')[-1] if file_obj.mime_type else 'mp3'}"
            file_size = file_obj.file_size
            file_id = file_obj.file_id
        elif update.message.video:
            file_obj = update.message.video
            file_name = file_obj.file_name or f"video_{file_obj.file_id[:8]}.mp4"
            file_size = file_obj.file_size
            file_id = file_obj.file_id
        elif update.message.voice:
            file_obj = update.message.voice
            file_name = f"voice_{file_obj.file_id[:8]}.ogg"
            file_size = file_obj.file_size
            file_id = file_obj.file_id
        elif update.message.video_note:
            file_obj = update.message.video_note
            file_name = f"video_note_{file_obj.file_id[:8]}.mp4"
            file_size = file_obj.file_size
            file_id = file_obj.file_id
        else:
            await update.message.reply_text(
                "❌ No supported file found! Please send a video or audio file.",
                parse_mode="Markdown",
            )
            return

        logger.info(f"User {user_id} uploaded file: {file_name}")
        logger.debug(f"File details - Name: {file_name}, Size: {file_size}, ID: {file_id}")

        # Check file type first
        if not self._is_supported_file_type(file_name):
            await update.message.reply_text(
                "❌ Unsupported file format! Please send a video or audio file.\n\n"
                "**Supported formats:**\n"
                "• Video: MP4, AVI, MOV, MKV, WMV, WebM\n"
                "• Audio: MP3, WAV, AAC, FLAC, OGG, M4A\n"
                "• Voice messages and video notes are also supported!",
                parse_mode="Markdown",
            )
            return

        # Check file size 
        if file_size is None or file_size == 0:
            logger.warning(f"File size is None or 0 for file: {file_name}")
            await update.message.reply_text(
                f"⚠️ **Cannot determine file size**\n\n"
                f"Unable to get file size information. This might be a temporary issue.\n"
                f"Please try uploading the file again.",
                parse_mode="Markdown",
            )
            return
            
        file_size_mb = file_size / (1024 * 1024)
        settings = get_settings()
        
        # Check if file is too large (over 2GB)
        if file_size_mb > settings.max_file_size_mb:
            await update.message.reply_text(
                f"📁 **File too large ({file_size_mb:.1f}MB)**\n\n"
                f"Maximum supported file size is {settings.max_file_size_mb}MB (2GB).\n\n"
                f"**Solutions:**\n"
                f"• Compress your file to reduce size\n"
                f"• For videos: extract audio only (much smaller)\n"
                f"• Split long recordings into shorter segments\n\n"
                f"Then send the smaller file and I'll transcribe it! 🚀",
                parse_mode="Markdown",
            )
            return

        # Send processing message
        processing_msg = await update.message.reply_text(
            f"🔄 **Processing {file_name}**\n\n"
            f"📁 Size: {file_size_mb:.1f}MB\n"
            f"⏳ This will take a few minutes...",
            parse_mode="Markdown",
        )

        temp_files_to_cleanup = []

        try:
            # Use MTProto for all file downloads (supports files up to 2GB)
            await processing_msg.edit_text(
                f"🔄 **Processing {file_name}**\n\n"
                f"📁 Size: {file_size_mb:.1f}MB\n"
                f"📥 Downloading...",
                parse_mode="Markdown",
            )

            # Progress callback for downloads
            last_progress = 0
            async def progress_callback(current: int, total: int):
                nonlocal last_progress
                progress = int((current / total) * 100)
                
                # Update every 10% to avoid rate limits
                if progress >= last_progress + 10:
                    last_progress = progress
                    try:
                        await processing_msg.edit_text(
                            f"🔄 **Processing {file_name}**\n\n"
                            f"📁 Size: {file_size_mb:.1f}MB\n"
                            f"📥 Downloading... {progress}%",
                            parse_mode="Markdown",
                        )
                    except Exception:
                        # Ignore rate limit errors during progress updates
                        pass

            temp_file_path = await self.mtproto_downloader.download_file_by_message(
                chat_id, message_id, progress_callback
            )
            
            if not temp_file_path:
                await processing_msg.edit_text(
                    f"❌ **Failed to download {file_name}**\n\n"
                    f"Could not download the file. Please try again.",
                    parse_mode="Markdown",
                )
                return
                
            temp_files_to_cleanup.append(temp_file_path)
            logger.info(f"Downloaded {file_size_mb:.1f}MB file via MTProto")

            # Start transcription
            await processing_msg.edit_text(
                f"🔄 **Processing {file_name}**\n\n"
                f"📁 Size: {file_size_mb:.1f}MB\n"
                f"🎙️ Transcribing...",
                parse_mode="Markdown",
            )

            # Transcribe the file
            transcript = await self.transcription_service.transcribe_file(temp_file_path)

            if not transcript:
                await processing_msg.edit_text(
                    f"❌ **Could not transcribe {file_name}**\n\n"
                    f"This might be due to audio quality or format issues.\n"
                    f"Please try with a different file.",
                    parse_mode="Markdown",
                )
                return

            # Update progress for speaker identification
            await processing_msg.edit_text(
                f"🔄 **Processing {file_name}**\n\n"
                f"📁 Size: {file_size_mb:.1f}MB\n"
                f"👥 Identifying speakers...",
                parse_mode="Markdown",
            )

            # Identify and replace speaker names
            transcript = await self.speaker_identification_service.process_transcript_with_speaker_names(transcript)

            # Create transcript file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            transcript_filename = f"transcript_{timestamp}.txt"
            transcript_file_path = await self.file_service.create_text_file(
                transcript, transcript_filename
            )
            temp_files_to_cleanup.append(transcript_file_path)

            # Update progress
            await processing_msg.edit_text(
                f"🔄 **Processing {file_name}**\n\n"
                f"📁 Size: {file_size_mb:.1f}MB\n"
                f"📝 Creating summary...",
                parse_mode="Markdown",
            )

            # Send transcript file
            with open(transcript_file_path, "rb") as transcript_file:
                await context.bot.send_document(
                    chat_id=update.effective_chat.id,
                    document=transcript_file,
                    filename=transcript_filename,
                    caption=f"📄 **Transcript ready!**\n\n"
                    f"From: {file_name}",
                    parse_mode="Markdown",
                )

            # Create summary
            summary = await self.summarization_service.create_summary_with_action_points(
                transcript
            )

            if summary:
                # Send summary as formatted message
                summary_message = f"📋 **Summary & Action Points**\n\n{summary}"

                # Split long messages if needed
                if len(summary_message) <= 4096:
                    try:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=summary_message,
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send with Markdown, trying without formatting: {e}")
                        # Fallback to plain text if markdown fails
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=summary_message,
                        )
                else:
                    chunks = self._split_message(summary_message, 4000)
                    for i, chunk in enumerate(chunks):
                        try:
                            if i == 0:
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text=chunk,
                                    parse_mode="Markdown",
                                )
                            else:
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text=f"📋 **Summary & Action Points (Part {i+1})**\n\n{chunk}",
                                    parse_mode="Markdown",
                                )
                        except Exception as e:
                            logger.warning(f"Failed to send chunk {i+1} with Markdown, trying without formatting: {e}")
                            # Fallback to plain text if markdown fails
                            if i == 0:
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text=chunk,
                                )
                            else:
                                await context.bot.send_message(
                                    chat_id=update.effective_chat.id,
                                    text=f"📋 Summary & Action Points (Part {i+1})\n\n{chunk}",
                                )

                try:
                    await processing_msg.edit_text(
                        f"✅ **{file_name} processed successfully!**\n\n"
                        f"📄 Transcript and summary are ready above.",
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Failed to send success message with Markdown: {e}")
                    await processing_msg.edit_text(
                        f"✅ {file_name} processed successfully!\n\n"
                        f"📄 Transcript and summary are ready above.",
                    )
            else:
                await processing_msg.edit_text(
                    f"✅ **{file_name} transcribed!**\n\n"
                    f"📄 Transcript is ready above.\n"
                    f"⚠️ Summary generation failed, but you have the full transcript.",
                    parse_mode="Markdown",
                )

            logger.info(
                f"Successfully processed {file_size_mb:.1f}MB file for user {user_id}"
            )

        except Exception as e:
            logger.error(f"Error processing file for user {user_id}: {e}", exc_info=True)
            await processing_msg.edit_text(
                f"❌ **Error processing {file_name}**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again with a different file.",
                parse_mode="Markdown",
            )
        finally:
            # Cleanup all temporary files
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

    async def handle_unsupported_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle unsupported message types."""
        await update.message.reply_text(
            "📎 Please send me a video or audio file to transcribe!\n\n"
            "Use /help to see supported formats and usage instructions.",
            parse_mode="Markdown",
        )

    def _is_supported_file_type(self, filename: str | None) -> bool:
        """Check if the file type is supported."""
        if not filename:
            return False

        # Voice messages and video notes are always supported (Telegram handles format)
        if filename.startswith("voice_") or filename.startswith("video_note_"):
            return True

        extension = os.path.splitext(filename)[1].lower()

        supported_extensions = {
            # Video formats
            ".mp4",
            ".avi",
            ".mov",
            ".mkv",
            ".wmv",
            ".flv",
            ".webm",
            # Audio formats
            ".mp3",
            ".wav",
            ".aac",
            ".flac",
            ".ogg",
            ".m4a",
            ".wma",
            ".opus",
        }

        return extension in supported_extensions

    def _split_message(self, message: str, max_length: int) -> list[str]:
        """Split a long message into chunks."""
        if len(message) <= max_length:
            return [message]

        chunks = []
        current_chunk = ""

        for line in message.split("\n"):
            if len(current_chunk) + len(line) + 1 <= max_length:
                current_chunk += line + "\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.rstrip())
                current_chunk = line + "\n"

        if current_chunk:
            chunks.append(current_chunk.rstrip())

        return chunks

    def setup_handlers(self, application: Application) -> None:
        """Set up all command and message handlers."""
        # Command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))

        # File handlers (documents, audio, video, voice, video notes)
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_file))
        application.add_handler(MessageHandler(filters.AUDIO, self.handle_file))
        application.add_handler(MessageHandler(filters.VIDEO, self.handle_file))
        application.add_handler(MessageHandler(filters.VOICE, self.handle_file))
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, self.handle_file))

        # Handle other message types
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self.handle_unsupported_message
            )
        )

    async def run(self) -> None:
        """Run the bot."""
        logger.info("Starting Telegram bot with large file support...")

        # Initialize services
        await self.initialize()

        try:
            # Create application
            settings = get_settings()
            application = Application.builder().token(settings.telegram_bot_token).build()

            # Setup handlers
            self.setup_handlers(application)

            # Initialize and start the bot
            await application.initialize()
            await application.start()
            
            # Start polling
            await application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
            
            # Keep running until interrupted
            logger.info("Bot is running. Press Ctrl+C to stop.")
            
            # Wait indefinitely
            try:
                while True:
                    await asyncio.sleep(1)
            except KeyboardInterrupt:
                logger.info("Received interrupt signal")
                
        finally:
            # Cleanup
            try:
                if application.updater.running:
                    await application.updater.stop()
                await application.stop()
                await application.shutdown()
            except Exception as e:
                logger.warning(f"Error during application shutdown: {e}")
            
            await self.cleanup()
