"""Main Telegram bot implementation with MTProto support for large files."""

import asyncio
import os
import tempfile
from datetime import datetime

from loguru import logger
from telegram import Document, Update, InlineKeyboardButton, InlineKeyboardMarkup
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
    DiagramService,
    QuestionAnsweringService,
)
from telegram_bot.mtproto_downloader import MTProtoDownloader
from analytics import analytics, tg_distinct_id


class TelegramTranscriptionBot:
    """Main bot class for handling Telegram interactions with large file support."""

    def __init__(self) -> None:
        """Initialize the bot with services."""
        self.transcription_service = TranscriptionService()
        self.summarization_service = SummarizationService()
        self.speaker_identification_service = SpeakerIdentificationService()
        self.file_service = FileService()
        self.diagram_service = DiagramService()
        self.question_answering_service = QuestionAnsweringService()
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
/diagram - Create a diagram from a transcript (reply to a .txt file)
/connect - Connect your Zoom account to receive recordings here
/status - Show Zoom connection status
/disconnect - Disconnect your Zoom account

**🆕 New Features:**

**🤖 Ask Questions About Transcripts (Claude Sonnet 4):**
• Reply to any transcript file with your question
• Get detailed answers about the content using Claude Sonnet 4
• Examples: "What were the main decisions made?", "Who spoke the most?", "What are the action items?"

**📊 Diagram Generation:**
• Reply to any transcript file with `/diagram` to create a visual diagram
• Use `/diagram <custom prompt>` to specify what the diagram should show
• Examples: `/diagram show the decision flow`, `/diagram map relationships`

Just send me a file and I'll handle the rest! 🚀
        """

        await update.message.reply_text(welcome_message, parse_mode="Markdown")
        logger.info(f"User {update.effective_user.id} started the bot")

        # Analytics: identify and capture command usage
        try:
            user = update.effective_user
            distinct_id = tg_distinct_id(user.id)
            self._identify_telegram_user(user)
            analytics.capture(
                distinct_id,
                "command_start",
                {
                    "ai_provider": ai_provider,
                },
            )
        except Exception:
            pass

    async def connect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Provide Zoom OAuth link to connect account."""
        settings = get_settings()
        base = settings.backend_base_url or ""
        if not base:
            await update.message.reply_text(
                "Zoom backend not configured. Ask admin to set BACKEND_BASE_URL.",
            )
            return
        import urllib.parse
        url = (
            f"{base.rstrip('/')}/zoom/connect?telegram_chat_id={update.effective_chat.id}"
            f"&telegram_user_id={update.effective_user.id}&redirect=true"
        )
        keyboard = [[InlineKeyboardButton(text="Connect Zoom", url=url)]]
        await update.message.reply_text(
            "🔗 Connect your Zoom account:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            disable_web_page_preview=True,
        )
        try:
            user = update.effective_user
            self._identify_telegram_user(user)
            analytics.capture(
                tg_distinct_id(user.id),
                "command_connect_zoom",
                {"backend_base_url_configured": bool(base)},
            )
        except Exception:
            pass

    async def status_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Check Zoom connection status (best-effort)."""
        settings = get_settings()
        base = settings.backend_base_url or ""
        if not base:
            await update.message.reply_text("Backend not configured (BACKEND_BASE_URL)")
            try:
                user = update.effective_user
                self._identify_telegram_user(user)
                analytics.capture(tg_distinct_id(user.id), "command_status", {"backend_configured": False})
            except Exception:
                pass
            return
        # Minimal status endpoint, for now just say it's running
        await update.message.reply_text("Backend reachable. If connected, you'll receive recordings here after meetings.")
        try:
            user = update.effective_user
            self._identify_telegram_user(user)
            analytics.capture(tg_distinct_id(user.id), "command_status", {"backend_configured": True})
        except Exception:
            pass

    async def disconnect_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Explain how to disconnect (through Zoom app uninstall)."""
        await update.message.reply_text(
            "To disconnect: open your Zoom Marketplace, uninstall the app. We'll remove your tokens automatically.")
        try:
            user = update.effective_user
            self._identify_telegram_user(user)
            analytics.capture(tg_distinct_id(user.id), "command_disconnect_zoom")
        except Exception:
            pass

    async def help_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /help command."""
        await self.start_command(update, context)
        try:
            user = update.effective_user
            self._identify_telegram_user(user)
            analytics.capture(tg_distinct_id(user.id), "command_help")
        except Exception:
            pass

    async def diagram_command(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle the /diagram command."""
        user_id = update.effective_user.id
        distinct_id = tg_distinct_id(user_id)
        # Identify user even if they didn't run /start
        try:
            self._identify_telegram_user(update.effective_user)
        except Exception:
            pass
        
        # Check if this is a reply to a message
        if not update.message.reply_to_message:
            await update.message.reply_text(
                "📊 **Diagram Command Usage**\n\n"
                "To create a diagram from a transcript:\n"
                "1. Reply to a transcript file with `/diagram`\n"
                "2. Or reply with `/diagram <custom prompt>`\n\n"
                "**Examples:**\n"
                "• `/diagram` - Creates a generic diagram\n"
                "• `/diagram show the decision flow` - Creates a diagram focused on decisions\n"
                "• `/diagram map the relationships between people` - Creates a relationship diagram\n\n"
                "The diagram will be generated based on the transcript content! 🎨",
                parse_mode="Markdown",
            )
            try:
                analytics.capture(distinct_id, "diagram_usage_help_shown")
            except Exception:
                pass
            return

        replied_message = update.message.reply_to_message
        
        # Check if the replied message has a document (transcript file)
        if not replied_message.document:
            await update.message.reply_text(
                "❌ **Please reply to a transcript file**\n\n"
                "The `/diagram` command works with transcript files (.txt) that I generated earlier.\n"
                "Reply to a transcript file with `/diagram` to create a diagram!",
                parse_mode="Markdown",
            )
            try:
                analytics.capture(distinct_id, "diagram_error_no_document")
            except Exception:
                pass
            return
        
        # Check if it's a .txt file (transcript)
        if not replied_message.document.file_name.endswith('.txt'):
            await update.message.reply_text(
                "❌ **Please reply to a transcript file**\n\n"
                "The `/diagram` command works with transcript files (.txt) that I generated earlier.\n"
                "Reply to a transcript file with `/diagram` to create a diagram!",
                parse_mode="Markdown",
            )
            try:
                analytics.capture(distinct_id, "diagram_error_not_txt", {"file_name": replied_message.document.file_name})
            except Exception:
                pass
            return
        
        # Extract custom prompt if provided
        custom_prompt = None
        if context.args:
            custom_prompt = ' '.join(context.args)
        try:
            analytics.capture(distinct_id, "diagram_requested", {"has_custom_prompt": bool(custom_prompt)})
        except Exception:
            pass
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            "📊 **Creating diagram from transcript...**\n\n"
            "🔄 This will take a moment...",
            parse_mode="Markdown",
        )
        
        temp_files_to_cleanup = []
        
        try:
            # Download the transcript file
            transcript_file = await replied_message.document.get_file()
            
            # Create a temporary file to store the transcript
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
                temp_file_path = temp_file.name
                
            temp_files_to_cleanup.append(temp_file_path)
            
            # Download the transcript content
            await transcript_file.download_to_drive(temp_file_path)
            
            # Read the transcript content
            with open(temp_file_path, 'r', encoding='utf-8') as f:
                transcript_content = f.read()
            
            if not transcript_content.strip():
                await processing_msg.edit_text(
                    "❌ **Empty transcript file**\n\n"
                    "The transcript file appears to be empty. Please try with a different file.",
                    parse_mode="Markdown",
                )
                try:
                    analytics.capture(distinct_id, "diagram_error_empty_transcript")
                except Exception:
                    pass
                return
            
            # Update processing message
            prompt_text = f" with custom prompt: '{custom_prompt}'" if custom_prompt else ""
            await processing_msg.edit_text(
                f"📊 **Creating diagram from transcript{prompt_text}...**\n\n"
                "🎨 Generating diagram...",
                parse_mode="Markdown",
            )
            
            # Generate diagram
            diagram_path = await self.diagram_service.create_diagram_from_transcript(
                transcript_content, custom_prompt
            )
            
            if not diagram_path:
                await processing_msg.edit_text(
                    "❌ **Failed to generate diagram**\n\n"
                    "Could not create a diagram from the transcript. This might be due to:\n"
                    "• Complex transcript content\n"
                    "• AI model limitations\n"
                    "• Technical issues\n\n"
                    "Please try again or use a different transcript.",
                    parse_mode="Markdown",
                )
                try:
                    analytics.capture(distinct_id, "diagram_failed")
                except Exception:
                    pass
                return
            
            temp_files_to_cleanup.append(diagram_path)
            
            # Send the diagram
            with open(diagram_path, 'rb') as diagram_file:
                caption = "📊 **Diagram Generated!**\n\n"
                if custom_prompt:
                    caption += f"Based on: {custom_prompt}\n"
                caption += f"From: {replied_message.document.file_name}"
                
                await context.bot.send_photo(
                    chat_id=update.effective_chat.id,
                    photo=diagram_file,
                    caption=caption,
                    parse_mode="Markdown",
                )
            
            # Update processing message with success
            await processing_msg.edit_text(
                "✅ **Diagram created successfully!**\n\n"
                "📊 Check the diagram above!",
                parse_mode="Markdown",
            )
            
            logger.info(f"Successfully created diagram for user {user_id}")
            try:
                analytics.capture(distinct_id, "diagram_succeeded")
            except Exception:
                pass
            
        except Exception as e:
            logger.error(f"Error creating diagram for user {user_id}: {e}", exc_info=True)
            await processing_msg.edit_text(
                f"❌ **Error creating diagram**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again with a different transcript.",
                parse_mode="Markdown",
            )
            try:
                analytics.capture(distinct_id, "diagram_error", {"error": str(e)[:200]})
            except Exception:
                pass
        finally:
            # Cleanup all temporary files
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

    async def handle_transcript_question(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle questions about transcript files when user replies to a transcript."""
        user_id = update.effective_user.id
        distinct_id = tg_distinct_id(user_id)
        question = update.message.text
        
        # Check if this is a reply to a message
        if not update.message.reply_to_message:
            return  # This handler should only be called for replies
            
        replied_message = update.message.reply_to_message
        
        # Check if the replied message has a document
        if not replied_message.document:
            return  # Not a document reply
            
        # Check if it's a transcript file (by filename pattern)
        file_name = replied_message.document.file_name
        if not file_name or not file_name.startswith("transcript_") or not file_name.endswith(".txt"):
            return  # Not a transcript file
            
        logger.info(f"User {user_id} asked question about transcript: {question[:100]}")
        try:
            self._identify_telegram_user(update.effective_user)
            analytics.capture(distinct_id, "transcript_question_received", {"question_len": len(question or "")})
        except Exception:
            pass
        
        # Send processing message
        processing_msg = await update.message.reply_text(
            f"🤔 **Analyzing transcript to answer your question...**\n\n"
            f"❓ Question: {question[:200]}{'...' if len(question) > 200 else ''}\n\n"
            f"🔄 Processing...",
            parse_mode="Markdown",
        )
        
        temp_files_to_cleanup = []
        
        try:
            # Download the transcript file
            transcript_file = await replied_message.document.get_file()
            
            # Create a temporary file to store the transcript
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.txt', delete=False) as temp_file:
                temp_file_path = temp_file.name
                
            temp_files_to_cleanup.append(temp_file_path)
            
            # Download the transcript content
            await transcript_file.download_to_drive(temp_file_path)
            
            # Read the transcript content
            transcript_content = await self.question_answering_service.read_transcript_file(temp_file_path)
            
            if not transcript_content:
                await processing_msg.edit_text(
                    "❌ **Could not read transcript file**\n\n"
                    "The transcript file appears to be empty or corrupted. Please try with a different file.",
                    parse_mode="Markdown",
                )
                return
            
            # Update processing message
            await processing_msg.edit_text(
                f"🤔 **Analyzing transcript to answer your question...**\n\n"
                f"❓ Question: {question[:200]}{'...' if len(question) > 200 else ''}\n\n"
                f"🧠 Generating answer with Claude Sonnet 4...",
                parse_mode="Markdown",
            )
            
            # Get answer from Claude Sonnet 4
            answer = await self.question_answering_service.answer_question_about_transcript(
                transcript_content, question
            )
            
            if not answer:
                await processing_msg.edit_text(
                    "❌ **Could not generate answer**\n\n"
                    "Sorry, I couldn't process your question about the transcript. This might be due to:\n"
                    "• AI model unavailability\n"
                    "• Complex question\n"
                    "• Technical issues\n\n"
                    "Please try rephrasing your question or try again later.",
                    parse_mode="Markdown",
                )
                try:
                    analytics.capture(distinct_id, "transcript_question_failed")
                except Exception:
                    pass
                return
            
            # Prepare the answer message
            answer_message = f"🤖 **Answer about transcript:**\n\n"
            answer_message += f"❓ **Question:** {question}\n\n"
            answer_message += f"💡 **Answer:**\n{answer}"
            
            # Send the answer, splitting if too long
            if len(answer_message) <= 4096:
                try:
                    await processing_msg.edit_text(
                        answer_message,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Failed to send answer with Markdown, trying without formatting: {e}")
                    # Fallback to plain text if markdown fails
                    await processing_msg.edit_text(answer_message)
            else:
                # Split long answers
                chunks = self._split_message(answer_message, 4000)
                
                # Edit the first message
                try:
                    await processing_msg.edit_text(
                        chunks[0],
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Failed to send first chunk with Markdown: {e}")
                    await processing_msg.edit_text(chunks[0])
                
                # Send remaining chunks as new messages
                for i, chunk in enumerate(chunks[1:], 2):
                    try:
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"🤖 **Answer (Part {i}):**\n\n{chunk}",
                            parse_mode="Markdown",
                        )
                    except Exception as e:
                        logger.warning(f"Failed to send chunk {i} with Markdown: {e}")
                        await context.bot.send_message(
                            chat_id=update.effective_chat.id,
                            text=f"🤖 Answer (Part {i}):\n\n{chunk}",
                        )
            
            logger.info(f"Successfully answered question for user {user_id}")
            try:
                analytics.capture(distinct_id, "transcript_question_answered", {"answer_len": len(answer or "")})
            except Exception:
                pass
            
        except Exception as e:
            logger.error(f"Error answering transcript question for user {user_id}: {e}", exc_info=True)
            await processing_msg.edit_text(
                f"❌ **Error processing your question**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again or rephrase your question.",
                parse_mode="Markdown",
            )
            try:
                analytics.capture(distinct_id, "transcript_question_error", {"error": str(e)[:200]})
            except Exception:
                pass
        finally:
            # Cleanup all temporary files
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

    async def handle_file(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle file uploads (documents, audio, video) with large file support up to 2GB."""
        user_id = update.effective_user.id
        distinct_id = tg_distinct_id(user_id)
        # Identify user even if they didn't run /start
        try:
            self._identify_telegram_user(update.effective_user)
        except Exception:
            pass
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
            try:
                analytics.capture(distinct_id, "file_not_found_in_message")
            except Exception:
                pass
            return

        logger.info(f"User {user_id} uploaded file: {file_name}")
        logger.debug(f"File details - Name: {file_name}, Size: {file_size}, ID: {file_id}")
        try:
            analytics.capture(
                distinct_id,
                "file_received",
                {
                    "file_name": file_name,
                    "file_size": int(file_size or 0),
                    "message_kind": (
                        "document" if update.message.document else
                        "audio" if update.message.audio else
                        "video" if update.message.video else
                        "voice" if update.message.voice else
                        "video_note" if update.message.video_note else
                        "unknown"
                    ),
                },
            )
        except Exception:
            pass

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
            try:
                analytics.capture(distinct_id, "file_unsupported", {"file_name": file_name})
            except Exception:
                pass
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
            try:
                analytics.capture(distinct_id, "file_size_unknown", {"file_name": file_name})
            except Exception:
                pass
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
            try:
                analytics.capture(distinct_id, "file_too_large", {"file_size_mb": float(file_size_mb)})
            except Exception:
                pass
            return

        # Send processing message
        escaped_file_name = self._escape_markdown(file_name)
        processing_msg = await update.message.reply_text(
            f"🔄 **Processing {escaped_file_name}**\n\n"
            f"📁 Size: {file_size_mb:.1f}MB\n"
            f"⏳ This will take a few minutes...",
            parse_mode="Markdown",
        )

        temp_files_to_cleanup = []

        try:
            # Use MTProto for all file downloads (supports files up to 2GB)
            await processing_msg.edit_text(
                f"🔄 **Processing {escaped_file_name}**\n\n"
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
                            f"🔄 **Processing {escaped_file_name}**\n\n"
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
                    f"❌ **Failed to download {escaped_file_name}**\n\n"
                    f"Could not download the file. Please try again.",
                    parse_mode="Markdown",
                )
                return
                
            temp_files_to_cleanup.append(temp_file_path)
            logger.info(f"Downloaded {file_size_mb:.1f}MB file via MTProto")
            try:
                analytics.capture(distinct_id, "download_succeeded", {"file_size_mb": float(file_size_mb)})
            except Exception:
                pass

            # Start transcription
            await processing_msg.edit_text(
                f"🔄 **Processing {escaped_file_name}**\n\n"
                f"📁 Size: {file_size_mb:.1f}MB\n"
                f"🎙️ Transcribing...",
                parse_mode="Markdown",
            )
            try:
                analytics.capture(distinct_id, "transcription_started", {"file_size_mb": float(file_size_mb)})
            except Exception:
                pass

            # Transcribe the file
            transcript = await self.transcription_service.transcribe_file(temp_file_path)

            if not transcript:
                await processing_msg.edit_text(
                    f"❌ **Could not transcribe {escaped_file_name}**\n\n"
                    f"This might be due to audio quality or format issues.\n"
                    f"Please try with a different file.",
                    parse_mode="Markdown",
                )
                try:
                    analytics.capture(distinct_id, "transcription_failed")
                except Exception:
                    pass
                return

            # Update progress for speaker identification
            await processing_msg.edit_text(
                f"🔄 **Processing {escaped_file_name}**\n\n"
                f"📁 Size: {file_size_mb:.1f}MB\n"
                f"👥 Identifying speakers...",
                parse_mode="Markdown",
            )

            # Identify and replace speaker names using existing AI-based method
            transcript = await self.speaker_identification_service.process_transcript_with_speaker_names(
                transcript
            )

            # Create transcript file
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            transcript_filename = f"transcript_{timestamp}.txt"
            transcript_file_path = await self.file_service.create_text_file(
                transcript, transcript_filename
            )
            temp_files_to_cleanup.append(transcript_file_path)

            # Update progress
            await processing_msg.edit_text(
                f"🔄 **Processing {escaped_file_name}**\n\n"
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
                    f"From: {escaped_file_name}",
                    parse_mode="Markdown",
                )
            try:
                analytics.capture(distinct_id, "transcription_succeeded", {"transcript_chars": len(transcript or "")})
            except Exception:
                pass

            # Create summary
            summary = await self.summarization_service.create_summary_with_action_points(
                transcript
            )

            if summary:
                # Send summary as formatted message (Telegram classic Markdown uses single * for bold)
                summary_message = f"📋 *Summary & Action Points*\n\n{summary}"

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
                                    text=f"📋 *Summary & Action Points (Part {i+1})*\n\n{chunk}",
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
                        f"✅ **{escaped_file_name} processed successfully!**\n\n"
                        f"📄 Transcript and summary are ready above.",
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    logger.warning(f"Failed to send success message with Markdown: {e}")
                    await processing_msg.edit_text(
                        f"✅ {escaped_file_name} processed successfully!\n\n"
                        f"📄 Transcript and summary are ready above.",
                    )
                try:
                    analytics.capture(distinct_id, "summary_succeeded", {"summary_chars": len(summary or "")})
                except Exception:
                    pass
            else:
                await processing_msg.edit_text(
                    f"✅ **{escaped_file_name} transcribed!**\n\n"
                    f"📄 Transcript is ready above.\n"
                    f"⚠️ Summary generation failed, but you have the full transcript.",
                    parse_mode="Markdown",
                )
                try:
                    analytics.capture(distinct_id, "summary_failed")
                except Exception:
                    pass

            logger.info(
                f"Successfully processed {file_size_mb:.1f}MB file for user {user_id}"
            )

        except Exception as e:
            logger.error(f"Error processing file for user {user_id}: {e}", exc_info=True)
            await processing_msg.edit_text(
                f"❌ **Error processing {escaped_file_name}**\n\n"
                f"Error: {str(e)}\n\n"
                f"Please try again with a different file.",
                parse_mode="Markdown",
            )
            try:
                analytics.capture(distinct_id, "processing_error", {"error": str(e)[:200]})
            except Exception:
                pass
        finally:
            # Cleanup all temporary files
            for temp_file in temp_files_to_cleanup:
                try:
                    if os.path.exists(temp_file):
                        os.remove(temp_file)
                        logger.debug(f"Cleaned up temp file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup temp file {temp_file}: {e}")

    async def handle_text_message(
        self, update: Update, context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Handle text messages - check if it's a transcript question first."""
        # Check if this is a reply to a transcript file
        if (update.message.reply_to_message and 
            update.message.reply_to_message.document and
            update.message.reply_to_message.document.file_name and
            update.message.reply_to_message.document.file_name.startswith("transcript_") and
            update.message.reply_to_message.document.file_name.endswith(".txt")):
            # This is a question about a transcript
            await self.handle_transcript_question(update, context)
        else:
            # Regular unsupported message
            await update.message.reply_text(
                "📎 Please send me a video or audio file to transcribe!\n\n"
                "💡 **New feature:** You can also reply to any transcript file with a question and I'll answer it using Claude Sonnet 4!\n\n"
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

    def _escape_markdown(self, text: str) -> str:
        """
        Escape special markdown characters in text to prevent parsing errors.
        
        Args:
            text: Text that might contain markdown special characters
            
        Returns:
            Text with markdown special characters escaped
        """
        if not text:
            return text
            
        # Escape markdown special characters
        special_chars = ['_', '*', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
        for char in special_chars:
            text = text.replace(char, f'\\{char}')
        return text

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

    def _identify_telegram_user(self, user) -> None:
        """Send user identity and metadata to analytics (PostHog)."""
        try:
            distinct_id = tg_distinct_id(user.id)
            analytics.identify(
                distinct_id,
                {
                    "platform": "telegram",
                    "telegram_id": user.id,
                    "username": getattr(user, "username", None),
                    "first_name": getattr(user, "first_name", None),
                    "last_name": getattr(user, "last_name", None),
                    "language_code": getattr(user, "language_code", None),
                    "is_bot": getattr(user, "is_bot", None),
                    "is_premium": getattr(user, "is_premium", None),
                },
            )
        except Exception:
            pass

    def setup_handlers(self, application: Application) -> None:
        """Set up all command and message handlers."""
        # Command handlers
        application.add_handler(CommandHandler("start", self.start_command))
        application.add_handler(CommandHandler("help", self.help_command))
        application.add_handler(CommandHandler("diagram", self.diagram_command))
        application.add_handler(CommandHandler("connect", self.connect_command))
        application.add_handler(CommandHandler("status", self.status_command))
        application.add_handler(CommandHandler("disconnect", self.disconnect_command))

        # File handlers (documents, audio, video, voice, video notes)
        application.add_handler(MessageHandler(filters.Document.ALL, self.handle_file))
        application.add_handler(MessageHandler(filters.AUDIO, self.handle_file))
        application.add_handler(MessageHandler(filters.VIDEO, self.handle_file))
        application.add_handler(MessageHandler(filters.VOICE, self.handle_file))
        application.add_handler(MessageHandler(filters.VIDEO_NOTE, self.handle_file))

        # Handle text messages (including transcript questions)
        application.add_handler(
            MessageHandler(
                filters.TEXT & ~filters.COMMAND, self.handle_text_message
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
