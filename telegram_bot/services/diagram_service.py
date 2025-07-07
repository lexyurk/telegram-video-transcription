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

    def _fix_mermaid_syntax(self, mermaid_code: str) -> str:
        """Fix common mermaid syntax issues to prevent parsing errors."""
        import re
        
        lines = mermaid_code.split('\n')
        fixed_lines = []
        
        for line in lines:
            # Remove any classDef lines entirely - they cause too many parsing issues
            if line.strip().startswith('classDef'):
                continue
            
            # Remove any lines with class applications that might reference removed classDef
            if ':::' in line:
                # Remove the class application but keep the node
                line = re.sub(r':::[\w]+', '', line)
            
            # Remove any lines with incomplete hex colors or other problematic syntax
            if '#' in line and re.search(r'#[0-9A-Fa-f]{1,5}(?=\s|,|;|$)', line):
                continue
            
            # Fix problematic characters in node labels
            # Replace parentheses in node labels with safer alternatives
            line = re.sub(r'\[([^\]]*)\(([^)]*)\)([^\]]*)\]', r'[\1-\2-\3]', line)
            
            # Fix any remaining problematic characters that can cause parsing issues
            # Replace other special chars in labels
            line = re.sub(r'\[([^\]]*[;:,{}]+[^\]]*)\]', lambda m: f'[{re.sub(r"[;:,{}]+", "-", m.group(1))}]', line)
            
            # Remove semicolons at the end of lines that might cause issues
            line = re.sub(r';\s*$', '', line)
            
            fixed_lines.append(line)
        
        return '\n'.join(fixed_lines)

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
4. Keep node labels concise but meaningful (max 15 chars per label)
5. AVOID special characters in labels: no parentheses (), semicolons ;, colons :, commas ,
6. Use only letters, numbers, spaces, and hyphens in node labels
7. Use proper mermaid syntax
8. Make sure the diagram is complete and syntactically correct
9. APPLY SIMPLE STYLING:
   - Use different node shapes: rectangles [], rounded (), diamonds {{}}
   - Use different arrow styles: --> (solid), -.-> (dotted), ===> (thick)  
   - Keep labels short and meaningful
   - Focus on clear structure and readability
   - DO NOT use classDef or color definitions - let the theme handle colors

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
4. Keep node labels concise but meaningful (max 15 chars per label)
5. AVOID special characters in labels: no parentheses (), semicolons ;, colons :, commas ,
6. Use only letters, numbers, spaces, and hyphens in node labels
7. Use proper mermaid syntax
8. Make sure the diagram is complete and syntactically correct
9. APPLY SIMPLE STYLING:
   - Use different node shapes: rectangles [], rounded (), diamonds {{}}
   - Use different arrow styles: --> (solid), -.-> (dotted), ===> (thick)  
   - Keep labels short and meaningful
   - Focus on clear structure and readability
   - DO NOT use classDef or color definitions - let the theme handle colors

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
                
                # Validate and fix common mermaid syntax issues
                mermaid_code = self._fix_mermaid_syntax(mermaid_code)
                
                logger.info(f"Successfully generated mermaid code: {len(mermaid_code)} characters")
                return mermaid_code
            else:
                logger.error("AI model returned empty mermaid code")
                return None

        except Exception as e:
            logger.error(f"Error generating mermaid code: {e}", exc_info=True)
            return None

    def _get_puppeteer_config(self) -> str:
        """Get Puppeteer configuration for cloud/containerized environments."""
        # Default Puppeteer args for headless environments
        puppeteer_args = [
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-accelerated-2d-canvas",
            "--no-first-run",
            "--no-zygote",
            "--single-process",
            "--disable-gpu",
            "--disable-extensions",
            "--disable-default-apps",
            "--disable-background-timer-throttling",
            "--disable-backgrounding-occluded-windows",
            "--disable-renderer-backgrounding",
            "--disable-features=TranslateUI",
            "--disable-ipc-flooding-protection",
            "--headless=new"
        ]
        
        # Check for Chrome executable path from environment
        chrome_path = os.environ.get('CHROME_BIN') or os.environ.get('PUPPETEER_EXECUTABLE_PATH')
        
        config = {
            "args": puppeteer_args,
            "headless": "new",
            "defaultViewport": {"width": 1200, "height": 800}
        }
        
        if chrome_path:
            config["executablePath"] = chrome_path
            logger.info(f"Using Chrome executable from environment: {chrome_path}")
        
        import json
        return json.dumps(config)

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
                # Use mermaid-cli to convert to image with forest theme
                # Add Puppeteer configuration for cloud/containerized environments
                puppeteer_config = self._get_puppeteer_config()
                logger.info(f"Using Puppeteer config: {puppeteer_config}")
                
                cmd = [
                    "mmdc",
                    "-i", mmd_file_path,
                    "-o", output_path,
                    "-t", "forest",  # Use forest theme (green/blue colors)
                    "-b", "#f8f9fa",  # Light gray background
                    "--width", "1200",  # Larger width for better readability
                    "--height", "800",  # Larger height
                    "--puppeteerConfig", puppeteer_config
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
                        "-t", "forest",
                        "-b", "#f8f9fa",
                        "--width", "1200",
                        "--height", "800",
                        "--puppeteerConfig", self._get_puppeteer_config()
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

    def _create_simple_diagram_prompt(self, transcript: str, custom_prompt: Optional[str] = None) -> str:
        """Create a simple prompt for basic diagram generation without styling."""
        base_prompt = f"""Based on the following transcript, create a simple mermaid diagram that represents the main topics and flow of the conversation.

IMPORTANT RULES:
1. Generate ONLY the mermaid diagram code - no explanations or markdown formatting
2. Start directly with the diagram type (e.g., "flowchart TD", "sequenceDiagram", etc.)
3. Keep it SIMPLE - no styling, no colors, no complex formatting
4. Use basic node shapes only: rectangles [text], rounded (text)
5. Use simple arrows: --> only
6. Keep node labels short and clear (max 15 chars)
7. Focus on clarity and correctness, not appearance

"""
        
        if custom_prompt:
            base_prompt += f"USER REQUIREMENTS: {custom_prompt}\n\n"
        
        base_prompt += f"Transcript:\n{transcript}"
        return base_prompt

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
            # Try to generate styled mermaid code first
            mermaid_code = await self._generate_mermaid_code(transcript, custom_prompt)
            
            if not mermaid_code:
                logger.error("Failed to generate mermaid code")
                return None

            # Convert to image
            image_path = await self._convert_mermaid_to_image(mermaid_code)
            
            if image_path:
                return image_path
            
            # If styled version failed, try simple version
            logger.info("Styled diagram failed, trying simple version...")
            
            # Generate simple diagram without styling
            simple_prompt = self._create_simple_diagram_prompt(
                self._remove_speaker_labels(transcript), custom_prompt
            )
            
            simple_mermaid_code = await self.ai_model.generate_text(simple_prompt)
            
            if simple_mermaid_code:
                # Clean up the code
                simple_mermaid_code = simple_mermaid_code.strip()
                if simple_mermaid_code.startswith('```mermaid'):
                    simple_mermaid_code = simple_mermaid_code[10:]
                if simple_mermaid_code.startswith('```'):
                    simple_mermaid_code = simple_mermaid_code[3:]
                if simple_mermaid_code.endswith('```'):
                    simple_mermaid_code = simple_mermaid_code[:-3]
                simple_mermaid_code = simple_mermaid_code.strip()
                
                logger.info(f"Generated simple mermaid code: {len(simple_mermaid_code)} characters")
                
                # Try to convert simple version
                simple_image_path = await self._convert_mermaid_to_image(simple_mermaid_code)
                
                if simple_image_path:
                    logger.info("Simple diagram generated successfully as fallback")
                    return simple_image_path
            
            logger.error("Both styled and simple diagram generation failed")
            return None

        except Exception as e:
            logger.error(f"Error creating diagram from transcript: {e}", exc_info=True)
            return None