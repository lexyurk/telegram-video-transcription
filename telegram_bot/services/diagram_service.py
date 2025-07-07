"""Diagram service for creating mermaid diagrams from transcripts."""

import asyncio
import os
import tempfile
from datetime import datetime
from typing import Optional

from loguru import logger

from telegram_bot.services.ai_model import AIModel


class DiagramService:
    """Service for creating mermaid diagrams from transcripts using AI models."""

    def __init__(self, ai_model: AIModel | None = None) -> None:
        """Initialize the diagram service."""
        from telegram_bot.services.ai_model import create_ai_model
        
        self.ai_model = ai_model or create_ai_model()

    def _remove_speaker_labels(self, text: str) -> str:
        """
        Remove speaker labels from transcript to avoid language confusion in AI.
        
        Args:
            text: Transcript with speaker labels
            
        Returns:
            Clean transcript without speaker labels
        """
        import re
        
        # Remove speaker labels like "Speaker 0:", "Серафима:", etc.
        lines = text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            # Remove speaker labels at the beginning of lines
            cleaned_line = re.sub(r'^[^:]+:\s*', '', line.strip())
            if cleaned_line:  # Only add non-empty lines
                cleaned_lines.append(cleaned_line)
        
        return ' '.join(cleaned_lines)

    def _create_generic_diagram_prompt(self, transcript: str) -> str:
        """Create a generic prompt for diagram generation."""
        return f"""Based on the following transcript, create a beautiful, well-styled mermaid diagram that best represents the main topics, relationships, and flow of the conversation.

IMPORTANT RULES:
1. Generate ONLY the mermaid diagram code - no explanations or markdown formatting
2. Start directly with the diagram type (e.g., "flowchart TD", "graph TD", "sequenceDiagram", etc.)
3. Choose the most appropriate diagram type based on content:
   - For system design discussions: use flowchart or graph
   - For processes or workflows: use flowchart TD (top-down)
   - For conversations between people: use sequenceDiagram
   - For organizational structures: use graph or mindmap
   - For timelines: use timeline or gantt
4. Keep node labels concise but meaningful (max 20 chars per label)
5. Use proper mermaid syntax
6. Make sure the diagram is complete and syntactically correct
7. APPLY BEAUTIFUL STYLING:
   - Use meaningful node shapes: rectangles [], rounded (), diamonds {{}}, circles ((()))
   - Add colors with classDef: classDef className fill:#color,stroke:#color,color:#fff
   - Apply classes to nodes: A:::className
   - Use different arrow styles: --> (solid), -.-> (dotted), ===> (thick)

STYLING EXAMPLES:
- For flowcharts: Add classDef and apply colors
- For sequence diagrams: Use participant aliases and notes
- Make it visually appealing with proper spacing and colors

Analyze the transcript and determine what type of diagram would best represent the content. Common patterns:
- If discussing system architecture → flowchart showing components and connections
- If discussing a process → flowchart showing steps and decisions
- If discussing relationships between people/entities → graph showing connections
- If discussing a timeline of events → timeline or gantt chart
- If discussing multiple topics → mindmap or flowchart with different branches

Transcript:
{transcript}"""

    def _create_custom_diagram_prompt(self, transcript: str, custom_prompt: str) -> str:
        """Create a custom prompt for diagram generation."""
        return f"""Based on the following transcript, create a beautiful, well-styled mermaid diagram with the following specifications:

USER REQUIREMENTS: {custom_prompt}

IMPORTANT RULES:
1. Generate ONLY the mermaid diagram code - no explanations or markdown formatting
2. Start directly with the diagram type (e.g., "flowchart TD", "graph TD", "sequenceDiagram", etc.)
3. Follow the user's requirements about what should be included in the diagram
4. Keep node labels concise but meaningful (max 20 chars per label)
5. Use proper mermaid syntax
6. Make sure the diagram is complete and syntactically correct
7. APPLY BEAUTIFUL STYLING:
   - Use meaningful node shapes: rectangles [], rounded (), diamonds {{}}, circles ((()))
   - Add colors with classDef: classDef className fill:#color,stroke:#color,color:#fff
   - Apply classes to nodes: A:::className
   - Use different arrow styles: --> (solid), -.-> (dotted), ===> (thick)

STYLING EXAMPLES:
- For flowcharts: Add classDef and apply colors
- For sequence diagrams: Use participant aliases and notes
- Make it visually appealing with proper spacing and colors

Transcript:
{transcript}"""

    async def _generate_mermaid_code(self, transcript: str, custom_prompt: Optional[str] = None) -> Optional[str]:
        """Generate mermaid diagram code from transcript."""
        try:
            if not transcript.strip():
                logger.warning("Empty transcript provided for diagram generation")
                return None

            # Remove speaker labels to avoid confusion in AI
            clean_transcript = self._remove_speaker_labels(transcript)
            logger.info(f"Removed speaker labels for diagram generation. Original: {len(transcript)} chars, Clean: {len(clean_transcript)} chars")

            # Create appropriate prompt
            if custom_prompt:
                prompt = self._create_custom_diagram_prompt(clean_transcript, custom_prompt)
            else:
                prompt = self._create_generic_diagram_prompt(clean_transcript)

            # Generate mermaid code
            mermaid_code = await self.ai_model.generate_text(prompt)
            
            if mermaid_code:
                # Clean up the generated code
                mermaid_code = mermaid_code.strip()
                
                # Remove markdown code blocks if present
                if mermaid_code.startswith('```mermaid'):
                    mermaid_code = mermaid_code[10:]
                if mermaid_code.startswith('```'):
                    mermaid_code = mermaid_code[3:]
                if mermaid_code.endswith('```'):
                    mermaid_code = mermaid_code[:-3]
                
                mermaid_code = mermaid_code.strip()
                
                logger.info(f"Successfully generated mermaid code: {len(mermaid_code)} characters")
                return mermaid_code
            else:
                logger.error("AI model returned empty mermaid code")
                return None

        except Exception as e:
            logger.error(f"Error generating mermaid code: {e}", exc_info=True)
            return None

    async def _convert_mermaid_to_image(self, mermaid_code: str) -> Optional[str]:
        """Convert mermaid code to image using mermaid-cli."""
        try:
            # Create temporary files
            with tempfile.NamedTemporaryFile(mode='w', suffix='.mmd', delete=False) as mmd_file:
                mmd_file.write(mermaid_code)
                mmd_file_path = mmd_file.name

            # Create output image path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/diagram_{timestamp}.png"

            try:
                # Use mermaid-cli to convert to image with better styling
                cmd = [
                    "mmdc",
                    "-i", mmd_file_path,
                    "-o", output_path,
                    "-t", "dark",  # Use dark theme
                    "-b", "white",  # White background for better contrast
                    "--width", "1200",  # Larger width for better readability
                    "--height", "800",  # Larger height
                    "-s", "2"  # Scale factor for higher quality
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                
                stdout, stderr = await process.communicate()
                
                logger.debug(f"mmdc command: {' '.join(cmd)}")
                logger.debug(f"mmdc stdout: {stdout.decode()}")
                logger.debug(f"mmdc stderr: {stderr.decode()}")
                
                if process.returncode == 0 and os.path.exists(output_path):
                    logger.info(f"Successfully converted mermaid to image: {output_path}")
                    return output_path
                else:
                    logger.error(f"Failed to convert mermaid to image. Return code: {process.returncode}")
                    logger.error(f"Command: {' '.join(cmd)}")
                    logger.error(f"Stdout: {stdout.decode()}")
                    logger.error(f"Stderr: {stderr.decode()}")
                    
                    # Try alternative approach with simpler command
                    logger.info("Trying alternative approach with simpler command...")
                    simple_cmd = [
                        "mmdc",
                        "-i", mmd_file_path,
                        "-o", output_path,
                        "-t", "dark",
                        "-b", "white",
                        "--width", "1200",
                        "--height", "800"
                    ]
                    
                    simple_process = await asyncio.create_subprocess_exec(
                        *simple_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    
                    simple_stdout, simple_stderr = await simple_process.communicate()
                    
                    if simple_process.returncode == 0 and os.path.exists(output_path):
                        logger.info(f"Successfully converted mermaid to image with simple command: {output_path}")
                        return output_path
                    else:
                        logger.error(f"Simple command also failed. Return code: {simple_process.returncode}")
                        logger.error(f"Simple stdout: {simple_stdout.decode()}")
                        logger.error(f"Simple stderr: {simple_stderr.decode()}")
                    
                    return None
                    
            finally:
                # Clean up temporary mermaid file
                try:
                    os.unlink(mmd_file_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp file {mmd_file_path}: {e}")

        except Exception as e:
            logger.error(f"Error converting mermaid to image: {e}", exc_info=True)
            return None

    async def create_diagram_from_transcript(self, transcript: str, custom_prompt: Optional[str] = None) -> Optional[str]:
        """
        Create a diagram image from transcript.

        Args:
            transcript: The transcript text to analyze
            custom_prompt: Optional custom prompt to guide diagram creation

        Returns:
            Path to the generated image file or None if failed
        """
        try:
            # Generate mermaid code
            mermaid_code = await self._generate_mermaid_code(transcript, custom_prompt)
            
            if not mermaid_code:
                logger.error("Failed to generate mermaid code")
                return None

            # Convert to image
            image_path = await self._convert_mermaid_to_image(mermaid_code)
            
            if not image_path:
                logger.error("Failed to convert mermaid to image")
                return None

            return image_path

        except Exception as e:
            logger.error(f"Error creating diagram from transcript: {e}", exc_info=True)
            return None