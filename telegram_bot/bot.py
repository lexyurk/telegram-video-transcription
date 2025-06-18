"""Main Telegram bot implementation with MTProto support for large files."""

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
from telegram_bot.services import FileService, SummarizationService, TranscriptionService, SpeakerIdentificationService
from telegram_bot.mtproto_downloader import MTProtoDownloader


class TelegramTranscriptionBot:
    """Main bot class for handling Telegram interactions with large file support."""

    def __init__(self) -> None:
        """Initialize the bot with services."""
        self.transcription_service = TranscriptionService()
        self.summarization_service = SummarizationService()
        self.file_service = FileService()
        self.speaker_identification_service = SpeakerIdentificationService()
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
        welcome_message = """
🎥 **Video/Audio Transcription Bot** 🎙️

Welcome! I can transcribe your video and audio files and create summaries with action points.

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

    async def handle_document(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle document/file uploads with large file support up to 2GB."""
        document: Document = update.message.document
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        message_id = update.message.message_id

        logger.info(f"User {user_id} uploaded file: {document.file_name}")

        # Check file type first
        if not self._is_supported_file_type(document.file_name):
            await update.message.reply_text(
                "❌ Unsupported file format! Please send a video or audio file.\n\n"
                "**Supported formats:**\n"
                "• Video: MP4, AVI, MOV, MKV, WMV, WebM\n"
                "• Audio: MP3, WAV, AAC, FLAC, OGG, M4A",
                parse_mode="Markdown",
            )
            return

        # Check file size 
        file_size_mb = document.file_size / (1024 * 1024)
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
            f"🔄 **Processing {document.file_name}**\n\n"
            f"📁 Size: {file_size_mb:.1f}MB\n"
            f"⏳ This will take a few minutes...",
            parse_mode="Markdown",
        )

        temp_files_to_cleanup = []

        try:
            # Determine download method based on file size
            if file_size_mb <= settings.telegram_api_limit_mb:
                # Use Bot API for smaller files (faster)
                await processing_msg.edit_text(
                    f"🔄 **Processing {document.file_name}**\n\n"
                    f"📁 Size: {file_size_mb:.1f}MB\n"
                    f"📥 Downloading...",
                    parse_mode="Markdown",
                )

                file = await context.bot.get_file(document.file_id)
                file_content = await file.download_as_bytearray()
                file_extension = os.path.splitext(document.file_name)[1].lower()
                temp_file_path = await self.file_service.save_temp_file(
                    bytes(file_content), file_extension
                )
                temp_files_to_cleanup.append(temp_file_path)
                
                logger.info(f"Downloaded {file_size_mb:.1f}MB file via Bot API")

            else:
                # Use MTProto for large files
                await processing_msg.edit_text(
                    f"🔄 **Processing {document.file_name}**\n\n"
                    f"📁 Size: {file_size_mb:.1f}MB\n"
                    f"📥 Downloading large file...",
                    parse_mode="Markdown",
                )

                # Progress callback for large downloads
                last_progress = 0
                async def progress_callback(current: int, total: int):
                    nonlocal last_progress
                    progress = int((current / total) * 100)
                    
                    # Update every 10% to avoid rate limits
                    if progress >= last_progress + 10:
                        last_progress = progress
                        try:
                            await processing_msg.edit_text(
                                f"🔄 **Processing {document.file_name}**\n\n"
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
                        f"❌ **Failed to download {document.file_name}**\n\n"
                        f"Could not download the large file. Please try again.",
                        parse_mode="Markdown",
                    )
                    return
                    
                temp_files_to_cleanup.append(temp_file_path)
                logger.info(f"Downloaded {file_size_mb:.1f}MB file via MTProto")

            # Start transcription
            await processing_msg.edit_text(
                f"🔄 **Processing {document.file_name}**\n\n"
                f"📁 Size: {file_size_mb:.1f}MB\n"
                f"🎙️ Transcribing...",
                parse_mode="Markdown",
            )

            # Transcribe the file
            transcript = await self.transcription_service.transcribe_file(temp_file_path)

            if not transcript:
                await processing_msg.edit_text(
                    f"❌ **Could not transcribe {document.file_name}**\n\n"
                    f"This might be due to audio quality or format issues.\n"
                    f"Please try with a different file.",
                    parse_mode="Markdown",
                )
                return

            # Update progress for speaker identification
            await processing_msg.edit_text(
                f"🔄 **Processing {document.file_name}**\n\n"
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
                f"🔄 **Processing {document.file_name}**\n\n"
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
                    f"From: {document.file_name}",
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
                    await context.bot.send_message(
                        chat_id=update.effective_chat.id,
                        text=summary_message,
                        parse_mode="Markdown",
                    )
                else:
                    chunks = self._split_message(summary_message, 4000)
                    for i, chunk in enumerate(chunks):
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

                await processing_msg.edit_text(
                    f"✅ **{document.file_name} processed successfully!**\n\n"
                    f"📄 Transcript and summary are ready above.",
                    parse_mode="Markdown",
                )
            else:
                await processing_msg.edit_text(
                    f"✅ **{document.file_name} transcribed!**\n\n"
                    f"📄 Transcript is ready above.\n"
                    f"⚠️ Summary generation failed, but you have the full transcript.",
                    parse_mode="Markdown",
                )

            logger.info(
                f"Successfully processed {file_size_mb:.1f}MB file for user {user_id}"
            )

        except Exception as e:
            logger.error(f"Error processing file for user {user_id}: {e}")
            await processing_msg.edit_text(
                f"❌ **Error processing {document.file_name}**\n\n"
                f"Something went wrong. Please try again with a different file.",
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

        # Document handler
        application.add_handler(
            MessageHandler(filters.Document.ALL, self.handle_document)
        )

        # Audio and video handlers
        application.add_handler(MessageHandler(filters.AUDIO, self.handle_document))
        application.add_handler(MessageHandler(filters.VIDEO, self.handle_document))

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

            # Run the bot
            await application.run_polling(allowed_updates=Update.ALL_TYPES)
        finally:
            # Cleanup
            await self.cleanup()
