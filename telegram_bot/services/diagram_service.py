"""Diagram service for creating diagrams from transcripts using pure Python."""

import os
import re
from typing import Optional

from loguru import logger

from telegram_bot.services.ai_model import AIModel, create_ai_model
from telegram_bot.services.python_diagram_generator import PythonDiagramGenerator
from telegram_bot.services.diagram_data_extractor import DiagramDataExtractor


class DiagramService:
    """Service for creating diagrams from transcripts using Python-only generation."""

    def __init__(self, ai_model: AIModel | None = None) -> None:
        """Initialize the diagram service."""
        self.ai_model = ai_model or create_ai_model()
        
        # Initialize Python-based diagram generator
        self.python_generator = PythonDiagramGenerator()
        self.data_extractor = DiagramDataExtractor(self.ai_model)
        
        logger.info("Diagram service initialized with Python-only generation")

    async def _create_python_diagram(self, transcript: str, custom_prompt: Optional[str] = None) -> Optional[str]:
        """Create a diagram using Python-based generator."""
        try:
            # Clean transcript
            clean_transcript = self._remove_speaker_labels(transcript)
            logger.info(f"Creating Python diagram from transcript: {len(clean_transcript)} chars")
            
            # Determine diagram type
            diagram_type = await self.data_extractor.analyze_transcript_for_diagram_type(clean_transcript)
            logger.info(f"Selected diagram type: {diagram_type}")
            
            # Extract data and create diagram based on type
            if diagram_type == 'flowchart':
                nodes, edges = await self.data_extractor.extract_flowchart_data(clean_transcript, custom_prompt)
                title = "Process Flow" if not custom_prompt else f"Process Flow: {custom_prompt[:30]}"
                return await self.python_generator.create_flowchart(nodes, edges, title)
                
            elif diagram_type == 'relationship':
                entities, relationships = await self.data_extractor.extract_relationship_data(clean_transcript, custom_prompt)
                title = "Relationships" if not custom_prompt else f"Relationships: {custom_prompt[:30]}"
                return await self.python_generator.create_relationship_diagram(entities, relationships, title)
                
            elif diagram_type == 'timeline':
                events = await self.data_extractor.extract_timeline_data(clean_transcript, custom_prompt)
                title = "Timeline" if not custom_prompt else f"Timeline: {custom_prompt[:30]}"
                return await self.python_generator.create_timeline_diagram(events, title)
                
            elif diagram_type == 'hierarchy':
                hierarchy = await self.data_extractor.extract_hierarchy_data(clean_transcript, custom_prompt)
                title = "Hierarchy" if not custom_prompt else f"Hierarchy: {custom_prompt[:30]}"
                return await self.python_generator.create_hierarchy_diagram(hierarchy, title)
                
            elif diagram_type == 'chart':
                chart_data, chart_type = await self.data_extractor.extract_chart_data(clean_transcript, custom_prompt)
                title = "Data Chart" if not custom_prompt else f"Chart: {custom_prompt[:30]}"
                return await self.python_generator.create_simple_chart(chart_data, chart_type, title)
                
            else:
                # Default to flowchart
                nodes, edges = await self.data_extractor.extract_flowchart_data(clean_transcript, custom_prompt)
                title = "Process Flow" if not custom_prompt else f"Process Flow: {custom_prompt[:30]}"
                return await self.python_generator.create_flowchart(nodes, edges, title)
                
        except Exception as e:
            logger.error(f"Error creating Python diagram: {e}", exc_info=True)
            return None

    def _remove_speaker_labels(self, text: str) -> str:
        """
        Remove speaker labels from transcript to avoid language confusion in AI.
        
        Args:
            text: Transcript with speaker labels
            
        Returns:
            Clean transcript without speaker labels
        """
        # Remove speaker labels like "Speaker 0:", "Серафима:", etc.
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove speaker labels at the beginning of lines
            cleaned_line = re.sub(r'^[^:]+:\s*', '', line.strip())
            if cleaned_line:  # Only add non-empty lines
                cleaned_lines.append(cleaned_line)
        
        return ' '.join(cleaned_lines)

    async def create_diagram_from_transcript(self, transcript: str, custom_prompt: Optional[str] = None) -> Optional[str]:
        """
        Create a diagram image from transcript using Python-only generation.

        Args:
            transcript: The transcript text to analyze
            custom_prompt: Optional custom prompt to guide diagram creation

        Returns:
            Path to the generated image file or None if failed
        """
        try:
            if not transcript.strip():
                logger.warning("Empty transcript provided for diagram generation")
                return None

            # Use Python-based diagram generator
            logger.info("Generating diagram with Python-only approach...")
            python_diagram_path = await self._create_python_diagram(transcript, custom_prompt)
            
            if python_diagram_path:
                logger.info(f"Successfully created Python diagram: {python_diagram_path}")
                return python_diagram_path
            else:
                logger.error("Python diagram generation failed")
                return None

        except Exception as e:
            logger.error(f"Error creating diagram from transcript: {e}", exc_info=True)
            return None