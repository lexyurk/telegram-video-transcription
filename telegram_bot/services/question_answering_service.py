"""Question answering service for transcript-based queries using Claude Sonnet 4."""

import os
from typing import Optional

from loguru import logger

from telegram_bot.services.ai_model import create_ai_model


class QuestionAnsweringService:
    """Service for answering questions about transcripts using Claude Sonnet 4."""

    def __init__(self) -> None:
        """Initialize the question answering service."""
        self.ai_model = create_ai_model()
        logger.info("Question answering service initialized")

    async def answer_question_about_transcript(
        self, transcript_content: str, question: str
    ) -> Optional[str]:
        """
        Answer a question about a transcript using Claude Sonnet 4.
        
        Args:
            transcript_content: The full transcript content
            question: The user's question about the transcript
            
        Returns:
            Answer to the question or None if failed
        """
        try:
            # Create a detailed prompt for Claude to analyze the transcript and answer the question
            prompt = f"""You are an AI assistant helping users understand and extract information from transcripts. You have been given a transcript and a question about it. Please analyze the transcript carefully and provide a helpful, accurate answer.

**Transcript:**
{transcript_content}

**Question:** {question}

**Instructions:**
- Read through the entire transcript carefully
- Answer the question based only on information present in the transcript
- If the answer isn't clear from the transcript, say so honestly
- Provide specific quotes or references when relevant
- Be concise but thorough in your response
- If the question asks for specific information (like names, dates, action items), extract them precisely
- If the question is about the overall content, provide a well-structured summary

**Answer:**"""

            logger.info(f"Generating answer for question: {question[:100]}...")
            
            answer = await self.ai_model.generate_text(prompt)
            
            if answer:
                logger.info("Successfully generated answer")
                return answer.strip()
            else:
                logger.error("Failed to generate answer - AI model returned None")
                return None
                
        except Exception as e:
            logger.error(f"Error answering question: {e}", exc_info=True)
            return None

    async def read_transcript_file(self, file_path: str) -> Optional[str]:
        """
        Read transcript content from a file.
        
        Args:
            file_path: Path to the transcript file
            
        Returns:
            Transcript content or None if failed
        """
        try:
            if not os.path.exists(file_path):
                logger.error(f"Transcript file not found: {file_path}")
                return None
                
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                
            if not content:
                logger.error(f"Transcript file is empty: {file_path}")
                return None
                
            logger.info(f"Successfully read transcript file: {file_path}")
            return content
            
        except Exception as e:
            logger.error(f"Error reading transcript file {file_path}: {e}", exc_info=True)
            return None