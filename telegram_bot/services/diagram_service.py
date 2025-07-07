"""Diagram service for creating mermaid diagrams from transcripts."""

import asyncio
import os
import subprocess
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
        
        # Run Chrome diagnostics on initialization
        self._run_chrome_diagnostics()

    def _run_chrome_diagnostics(self) -> None:
        """Run Chrome diagnostics to check installation and provide helpful error messages."""
        try:
            chrome_paths = [
                os.environ.get('CHROME_BIN'),
                os.environ.get('PUPPETEER_EXECUTABLE_PATH'),
                '/usr/local/bin/chrome-headless-shell',
                '/opt/puppeteer-cache/chrome-headless-shell/linux-*/chrome-headless-shell',
                '/usr/bin/google-chrome',
                '/usr/bin/chromium-browser',
                '/usr/bin/chrome'
            ]
            
            found_chrome = None
            for chrome_path in chrome_paths:
                if chrome_path and os.path.exists(chrome_path) and os.access(chrome_path, os.X_OK):
                    found_chrome = chrome_path
                    break
                elif chrome_path and '*' in chrome_path:
                    # Handle wildcard paths
                    import glob
                    matches = glob.glob(chrome_path)
                    for match in matches:
                        if os.path.exists(match) and os.access(match, os.X_OK):
                            found_chrome = match
                            break
                    if found_chrome:
                        break
            
            if found_chrome:
                logger.info(f"✅ Chrome found at: {found_chrome}")
                
                # Test Chrome version
                try:
                    result = subprocess.run([found_chrome, '--version'], 
                                         capture_output=True, text=True, timeout=5)
                    if result.returncode == 0:
                        logger.info(f"✅ Chrome version: {result.stdout.strip()}")
                    else:
                        logger.warning(f"⚠️ Chrome version check failed: {result.stderr}")
                except Exception as e:
                    logger.warning(f"⚠️ Chrome version check error: {e}")
                    
                # Test basic Chrome functionality
                try:
                    test_args = [found_chrome, '--headless=new', '--no-sandbox', '--disable-gpu', '--version']
                    result = subprocess.run(test_args, capture_output=True, text=True, timeout=10)
                    if result.returncode == 0:
                        logger.info("✅ Chrome basic functionality test passed")
                    else:
                        logger.warning(f"⚠️ Chrome basic test failed: {result.stderr}")
                except Exception as e:
                    logger.warning(f"⚠️ Chrome basic test error: {e}")
                    
            else:
                logger.error("❌ Chrome not found in any expected location")
                logger.error("Available paths checked:")
                for path in chrome_paths:
                    if path:
                        logger.error(f"  - {path} (exists: {os.path.exists(path) if path else False})")
                
        except Exception as e:
            logger.warning(f"Chrome diagnostics failed: {e}")

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

    def _get_puppeteer_config(self) -> dict:
        """Get Puppeteer configuration for cloud/containerized environments."""
        # Enhanced Puppeteer args for headless environments and containers
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
            "--headless=new",
            "--disable-web-security",
            "--disable-features=VizDisplayCompositor",
            "--disable-logging",
            "--disable-permissions-api",
            "--disable-background-networking",
            "--disable-sync",
            "--disable-translate",
            "--hide-scrollbars",
            "--mute-audio",
            "--no-default-browser-check",
            "--no-pings",
            "--disable-default-apps",
            "--disable-bundled-ppapi-flash",
            "--disable-plugins-discovery",
            "--disable-preconnect",
            "--disable-hang-monitor",
            "--disable-client-side-phishing-detection",
            "--disable-popup-blocking",
            "--disable-prompt-on-repost",
            "--disable-domain-reliability",
            "--disable-component-update",
            "--disable-background-downloads",
            "--disable-add-to-shelf",
            "--disable-datasaver-prompt",
            "--disable-device-discovery-notifications",
            "--disable-infobars",
            "--disable-notifications",
            "--disable-desktop-notifications",
            "--disable-save-password-bubble",
            "--disable-session-crashed-bubble",
            "--disable-speech-api",
            "--disable-tab-for-desktop-share",
            "--disable-voice-input",
            "--disable-wake-on-wifi",
            "--disable-printing",
            "--disable-crash-reporter",
            "--disable-breakpad",
            "--disable-check-for-update-interval",
            "--disable-cloud-import",
            "--disable-contextual-search",
            "--disable-dinosaur-easter-egg",
            "--disable-new-zip-unpacker",
            "--disable-search-engine-choice-screen",
            "--disable-features=OutOfBlinkCors,SameSiteByDefaultCookies,CookiesWithoutSameSiteMustBeSecure",
            "--use-mock-keychain",
            "--force-color-profile=srgb",
            "--memory-pressure-off",
            "--max_old_space_size=4096",
            "--js-flags=--expose-gc --max-old-space-size=4096"
        ]
        
        # Check for Chrome executable path from environment
        chrome_path = os.environ.get('CHROME_BIN') or os.environ.get('PUPPETEER_EXECUTABLE_PATH')
        
        config = {
            "args": puppeteer_args,
            "headless": "new",
            "defaultViewport": {
                "width": 1920,  # Full HD resolution
                "height": 1080,
                "deviceScaleFactor": 2  # High-DPI rendering
            },
            "ignoreHTTPSErrors": True,
            "ignoreDefaultArgs": ["--disable-extensions"],
            "pipe": True,
            "timeout": 30000,
            "protocolTimeout": 30000,
            "handleSIGINT": False,
            "handleSIGTERM": False,
            "handleSIGHUP": False,
            "devtools": False,
            "slowMo": 0
        }
        
        if chrome_path:
            config["executablePath"] = chrome_path
            logger.info(f"Using Chrome executable from environment: {chrome_path}")
        
        return config

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

            # Create temporary puppeteer config file
            puppeteer_config = self._get_puppeteer_config()
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as config_file:
                import json
                json.dump({"puppeteer": puppeteer_config}, config_file)
                config_file_path = config_file.name

            try:
                # Set environment variables that mermaid-cli will respect
                env = os.environ.copy()
                env.update({
                    'PUPPETEER_ARGS': '--no-sandbox,--disable-setuid-sandbox,--disable-dev-shm-usage,--disable-gpu,--disable-extensions,--no-first-run,--no-zygote,--single-process,--headless=new',
                    'PUPPETEER_EXECUTABLE_PATH': puppeteer_config.get('executablePath', '/usr/local/bin/chrome-headless-shell'),
                    'CHROME_BIN': puppeteer_config.get('executablePath', '/usr/local/bin/chrome-headless-shell'),
                    'MERMAID_CHROMIUM_ARGS': '--no-sandbox --disable-setuid-sandbox --disable-dev-shm-usage --disable-gpu --disable-extensions --no-first-run --no-zygote --single-process --headless=new'
                })
                
                # Use mermaid-cli to convert to image with forest theme
                logger.info(f"Using Puppeteer config: {puppeteer_config}")
                logger.info(f"Using Chrome path: {env.get('PUPPETEER_EXECUTABLE_PATH')}")
                
                cmd = [
                    "mmdc",
                    "-i", mmd_file_path,
                    "-o", output_path,
                    "-t", "forest",  # Use forest theme (green/blue colors)
                    "-b", "#f8f9fa",  # Light gray background
                    "--width", "1920",  # Full HD width
                    "--height", "1080",  # Full HD height
                    "--scale", "2",  # 2x scale for crisp rendering
                    "--configFile", config_file_path
                ]
                
                process = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
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
                    
                    # Try alternative approach with simpler command (no config file)
                    logger.info("Trying alternative approach without config file...")
                    simple_cmd = [
                        "mmdc",
                        "-i", mmd_file_path,
                        "-o", output_path,
                        "-t", "forest",
                        "-b", "#f8f9fa",
                        "--width", "1920",
                        "--height", "1080",
                        "--scale", "2"
                    ]
                    
                    simple_process = await asyncio.create_subprocess_exec(
                        *simple_cmd,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        env=env
                    )
                    
                    simple_stdout, simple_stderr = await simple_process.communicate()
                    
                    if simple_process.returncode == 0 and os.path.exists(output_path):
                        logger.info(f"Successfully converted mermaid to image with simple command: {output_path}")
                        return output_path
                    else:
                        logger.error(f"Simple command also failed. Return code: {simple_process.returncode}")
                        logger.error(f"Simple stdout: {simple_stdout.decode()}")
                        logger.error(f"Simple stderr: {simple_stderr.decode()}")
                        
                        # Try high-quality SVG first, then convert to PNG
                        logger.info("Trying high-quality SVG approach...")
                        svg_output_path = output_path.replace('.png', '.svg')
                        svg_cmd = [
                            "mmdc",
                            "-i", mmd_file_path,
                            "-o", svg_output_path,
                            "-t", "forest",
                            "-b", "#f8f9fa"
                        ]
                        
                        svg_process = await asyncio.create_subprocess_exec(
                            *svg_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            env=env
                        )
                        
                        svg_stdout, svg_stderr = await svg_process.communicate()
                        
                        if svg_process.returncode == 0 and os.path.exists(svg_output_path):
                            logger.info(f"Successfully created SVG: {svg_output_path}")
                            # Convert SVG to high-quality PNG using Chrome
                            png_result = await self._convert_svg_to_png(svg_output_path, output_path)
                            if png_result:
                                # Clean up SVG file
                                try:
                                    os.unlink(svg_output_path)
                                except:
                                    pass
                                return output_path
                        
                        # Try the most basic approach - no theme, no config
                        logger.info("Trying most basic approach with minimal arguments...")
                        basic_cmd = [
                            "mmdc",
                            "-i", mmd_file_path,
                            "-o", output_path,
                                                         "--width", "1920",
                             "--height", "1080",
                            "--scale", "2"
                        ]
                        
                        basic_process = await asyncio.create_subprocess_exec(
                            *basic_cmd,
                            stdout=asyncio.subprocess.PIPE,
                            stderr=asyncio.subprocess.PIPE,
                            env=env
                        )
                        
                        basic_stdout, basic_stderr = await basic_process.communicate()
                        
                        if basic_process.returncode == 0 and os.path.exists(output_path):
                            logger.info(f"Successfully converted mermaid to image with basic command: {output_path}")
                            return output_path
                        else:
                            logger.error(f"Basic command also failed. Return code: {basic_process.returncode}")
                            logger.error(f"Basic stdout: {basic_stdout.decode()}")
                            logger.error(f"Basic stderr: {basic_stderr.decode()}")
                    
                    return None
                    
            finally:
                # Clean up temporary files
                try:
                    os.unlink(mmd_file_path)
                    os.unlink(config_file_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp files: {e}")

        except Exception as e:
            logger.error(f"Error converting mermaid to image: {e}", exc_info=True)
            return None
    
    async def _convert_svg_to_png(self, svg_path: str, output_path: str) -> bool:
        """Convert SVG to high-quality PNG using Chrome."""
        try:
            # Get Chrome path
            chrome_path = os.environ.get('CHROME_BIN') or os.environ.get('PUPPETEER_EXECUTABLE_PATH') or '/usr/local/bin/chrome-headless-shell'
            
            # Set environment variables for Chrome
            env = os.environ.copy()
            env.update({
                'DISPLAY': ':99',
                'CHROME_BIN': chrome_path,
                'PUPPETEER_EXECUTABLE_PATH': chrome_path
            })
            
            # Chrome command for SVG to PNG conversion
            chrome_args = [
                chrome_path,
                '--headless=new',
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
                '--disable-extensions',
                '--no-first-run',
                '--no-zygote',
                '--single-process',
                '--disable-web-security',
                '--window-size=1920,1080',
                '--force-device-scale-factor=2',
                '--screenshot',
                f'--screenshot={output_path}',
                f'file://{svg_path}'
            ]
            
            process = await asyncio.create_subprocess_exec(
                *chrome_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                env=env
            )
            
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0 and os.path.exists(output_path):
                logger.info(f"Successfully converted SVG to PNG: {output_path}")
                return True
            else:
                logger.error(f"SVG to PNG conversion failed. Return code: {process.returncode}")
                logger.error(f"SVG conversion stderr: {stderr.decode()}")
                return False
                
        except Exception as e:
            logger.error(f"Error converting SVG to PNG: {e}", exc_info=True)
            return False
    
    async def _convert_mermaid_direct_chrome(self, mermaid_code: str) -> Optional[str]:
        """Direct Chrome approach as last resort."""
        try:
            import json
            import base64
            
            # Create output image path
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = f"/tmp/diagram_{timestamp}.png"
            
            # Create a simple HTML page with mermaid
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
                                 <style>
                     body {{
                         margin: 0;
                         padding: 40px;
                         font-family: Arial, sans-serif;
                         background-color: #f8f9fa;
                         min-width: 1920px;
                         min-height: 1080px;
                     }}
                     .mermaid {{
                         text-align: center;
                         font-size: 16px;
                         line-height: 1.5;
                     }}
                 </style>
            </head>
            <body>
                <div class="mermaid">
                    {mermaid_code}
                </div>
                                 <script>
                     mermaid.initialize({{ 
                         startOnLoad: true,
                         theme: 'forest',
                         themeVariables: {{
                             primaryColor: '#4CAF50',
                             primaryTextColor: '#ffffff',
                             primaryBorderColor: '#45a049',
                             lineColor: '#2E7D32',
                             secondaryColor: '#81C784',
                             tertiaryColor: '#C8E6C9'
                         }},
                         flowchart: {{
                             useMaxWidth: false,
                             htmlLabels: true,
                             curve: 'basis'
                         }},
                         sequence: {{
                             useMaxWidth: false,
                             wrap: true
                         }},
                         gantt: {{
                             useMaxWidth: false
                         }},
                         journey: {{
                             useMaxWidth: false
                         }},
                         fontFamily: 'Arial, sans-serif',
                         fontSize: '16px',
                         scale: 2
                     }});
                 </script>
            </body>
            </html>
            """
            
            # Create temporary HTML file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as html_file:
                html_file.write(html_content)
                html_file_path = html_file.name
            
            try:
                # Get Chrome path
                chrome_path = os.environ.get('CHROME_BIN') or os.environ.get('PUPPETEER_EXECUTABLE_PATH') or '/usr/local/bin/chrome-headless-shell'
                
                # Set environment variables for Chrome
                env = os.environ.copy()
                env.update({
                    'DISPLAY': ':99',
                    'CHROME_BIN': chrome_path,
                    'PUPPETEER_EXECUTABLE_PATH': chrome_path
                })
                
                # Direct Chrome command
                chrome_args = [
                    chrome_path,
                    '--headless=new',
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-gpu',
                    '--disable-extensions',
                    '--no-first-run',
                    '--no-zygote',
                    '--single-process',
                    '--disable-web-security',
                    '--disable-features=VizDisplayCompositor',
                    '--virtual-time-budget=10000',
                    '--run-all-compositor-stages-before-draw',
                    '--disable-background-timer-throttling',
                    '--disable-backgrounding-occluded-windows',
                    '--disable-renderer-backgrounding',
                    '--disable-features=TranslateUI',
                    '--disable-ipc-flooding-protection',
                    '--force-color-profile=srgb',
                    '--disable-background-networking',
                    '--disable-default-apps',
                    '--disable-sync',
                    '--disable-translate',
                    '--hide-scrollbars',
                    '--mute-audio',
                    '--no-default-browser-check',
                    '--no-pings',
                    '--disable-logging',
                    '--disable-permissions-api',
                    '--window-size=1920,1080',
                    '--force-device-scale-factor=2',
                    '--screenshot',
                    f'--screenshot={output_path}',
                    f'file://{html_file_path}'
                ]
                
                logger.info(f"Attempting direct Chrome approach with path: {chrome_path}")
                
                process = await asyncio.create_subprocess_exec(
                    *chrome_args,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    env=env
                )
                
                stdout, stderr = await process.communicate()
                
                if process.returncode == 0 and os.path.exists(output_path):
                    logger.info(f"Successfully created diagram with direct Chrome approach: {output_path}")
                    return output_path
                else:
                    logger.error(f"Direct Chrome approach failed. Return code: {process.returncode}")
                    logger.error(f"Chrome stdout: {stdout.decode()}")
                    logger.error(f"Chrome stderr: {stderr.decode()}")
                    return None
                    
            finally:
                # Clean up temporary HTML file
                try:
                    os.unlink(html_file_path)
                except Exception as e:
                    logger.warning(f"Failed to clean up temp HTML file: {e}")
                    
        except Exception as e:
            logger.error(f"Error in direct Chrome approach: {e}", exc_info=True)
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
            
            # Final fallback: try direct Chrome approach
            logger.info("All mermaid-cli approaches failed, trying direct Chrome approach...")
            direct_chrome_path = await self._convert_mermaid_direct_chrome(simple_mermaid_code or mermaid_code)
            
            if direct_chrome_path:
                logger.info("Direct Chrome approach succeeded as final fallback")
                return direct_chrome_path
            
            logger.error("All diagram generation methods failed (mermaid-cli and direct Chrome)")
            return None

        except Exception as e:
            logger.error(f"Error creating diagram from transcript: {e}", exc_info=True)
            return None