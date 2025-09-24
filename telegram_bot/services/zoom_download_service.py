"""Service for downloading audio from Zoom recording links with access codes."""

import re
import os
import tempfile
import asyncio
from typing import Optional, Tuple
import httpx
import logging
from urllib.parse import urlparse, parse_qs

logger = logging.getLogger(__name__)


class ZoomDownloadService:
    """Service to handle Zoom recording downloads with access codes."""

    def __init__(self):
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(600.0),  # 10 minute timeout for large files
            follow_redirects=True
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def parse_zoom_message(self, text: str) -> Optional[Tuple[str, str]]:
        """
        Parse a message containing a Zoom recording link and access code.

        Args:
            text: Message text containing Zoom link and access code

        Returns:
            Tuple of (recording_url, access_code) if found, None otherwise
        """
        # Pattern to match Zoom recording URLs (including short domain zoom.us)
        url_pattern = r'https://(?:[a-zA-Z0-9]+\.)?zoom\.us/rec/share/[a-zA-Z0-9\-_\.]+'

        # Pattern to match access code (various formats)
        # Matches patterns like: "Код доступа: m^hYZ7t4", "Access code: xyz123", "Passcode: abc"
        code_patterns = [
            r'Код доступа:\s*([^\s\n]+)',
            r'Access code:\s*([^\s\n]+)',
            r'Passcode:\s*([^\s\n]+)',
            r'Password:\s*([^\s\n]+)',
        ]

        # Find URL
        url_match = re.search(url_pattern, text)
        if not url_match:
            return None

        recording_url = url_match.group(0)

        # Find access code
        access_code = None
        for pattern in code_patterns:
            code_match = re.search(pattern, text, re.IGNORECASE)
            if code_match:
                access_code = code_match.group(1)
                break

        if not access_code:
            logger.warning(f"Found Zoom URL but no access code in message")
            return None

        return recording_url, access_code

    async def download_zoom_recording(
        self,
        recording_url: str,
        access_code: str,
        progress_callback=None
    ) -> Optional[str]:
        """
        Download audio from a Zoom recording using the provided access code.

        Args:
            recording_url: The Zoom recording share URL
            access_code: The access code/password for the recording
            progress_callback: Optional callback for download progress

        Returns:
            Path to the downloaded audio file, or None if download failed
        """
        try:
            logger.info(f"Starting Zoom recording download from: {recording_url}")

            # First, access the share page to get the actual recording URL
            response = await self.client.get(recording_url)

            if response.status_code != 200:
                logger.error(f"Failed to access Zoom share page: {response.status_code}")
                return None

            # Extract the meeting ID from the URL or page content
            # The actual download URL pattern varies, but typically includes the meeting ID
            parsed_url = urlparse(recording_url)
            path_parts = parsed_url.path.split('/')

            if 'share' in path_parts:
                share_index = path_parts.index('share')
                if share_index + 1 < len(path_parts):
                    recording_id = path_parts[share_index + 1].split('.')[0]
                else:
                    logger.error("Could not extract recording ID from URL")
                    return None
            else:
                logger.error("Invalid Zoom share URL format")
                return None

            # Construct the download URL with access code
            # Zoom typically uses a specific API endpoint for authenticated downloads
            base_domain = f"{parsed_url.scheme}://{parsed_url.netloc}"

            # Try to download the recording
            # Note: Zoom's actual API might require additional authentication steps
            download_urls = [
                f"{base_domain}/rec/download/{recording_id}?pwd={access_code}",
                f"{base_domain}/rec/play/{recording_id}?pwd={access_code}",
                f"{base_domain}/recording/download/{recording_id}?access_token={access_code}",
            ]

            temp_file = None
            for download_url in download_urls:
                try:
                    logger.info(f"Attempting download from: {download_url[:50]}...")

                    # Create a temporary file for the download
                    temp_file = tempfile.NamedTemporaryFile(
                        delete=False,
                        suffix='.mp4',  # Zoom recordings are typically MP4
                        dir=tempfile.gettempdir()
                    )

                    # Download with streaming to handle large files
                    async with self.client.stream('GET', download_url) as response:
                        if response.status_code == 200:
                            # Check content type to ensure it's not HTML
                            content_type = response.headers.get('content-type', '').lower()
                            if 'text/html' in content_type:
                                logger.debug("Got HTML response instead of video file")
                                if temp_file:
                                    temp_file.close()
                                    os.unlink(temp_file.name)
                                temp_file = None
                                continue

                            total_size = int(response.headers.get('content-length', 0))
                            downloaded = 0

                            async for chunk in response.aiter_bytes(chunk_size=8192):
                                temp_file.write(chunk)
                                downloaded += len(chunk)

                                if progress_callback and total_size > 0:
                                    progress = (downloaded / total_size) * 100
                                    await progress_callback(progress)

                            temp_file.close()

                            # Verify it's actually a video/audio file
                            import subprocess
                            try:
                                result = subprocess.run(
                                    ['file', temp_file.name],
                                    capture_output=True,
                                    text=True,
                                    timeout=5
                                )
                                file_type = result.stdout.lower()
                                if 'html' in file_type or 'text' in file_type:
                                    logger.debug("Downloaded file is HTML/text, not media")
                                    os.unlink(temp_file.name)
                                    continue
                            except Exception:
                                pass  # If 'file' command fails, continue anyway

                            logger.info(f"Successfully downloaded recording to: {temp_file.name}")
                            return temp_file.name
                        else:
                            logger.debug(f"Download attempt failed with status: {response.status_code}")
                            if temp_file:
                                temp_file.close()
                                os.unlink(temp_file.name)
                            temp_file = None

                except Exception as e:
                    logger.debug(f"Download attempt failed: {e}")
                    if temp_file:
                        try:
                            temp_file.close()
                            os.unlink(temp_file.name)
                        except:
                            pass
                    temp_file = None
                    continue

            # If we get here, all direct download attempts failed
            logger.info("Direct download failed, Zoom requires browser authentication")

            # As a fallback, try using yt-dlp if available
            # yt-dlp can handle many video platforms including Zoom
            return await self._download_with_ytdlp(recording_url, access_code)

        except Exception as e:
            logger.error(f"Error downloading Zoom recording: {e}")
            return None

    async def _download_with_ytdlp(self, recording_url: str, access_code: str) -> Optional[str]:
        """
        Fallback method using yt-dlp for downloading.

        Args:
            recording_url: The Zoom recording URL
            access_code: The access code for the recording

        Returns:
            Path to downloaded file or None if failed
        """
        try:
            import yt_dlp
        except ImportError:
            logger.info("yt-dlp not installed, skipping fallback download method")
            return None

        try:
            temp_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.mp4',
                dir=tempfile.gettempdir()
            )
            temp_file.close()

            ydl_opts = {
                'outtmpl': temp_file.name,
                'quiet': True,
                'no_warnings': True,
                'extract_audio': False,  # Keep original format
                'videopassword': access_code,  # Provide the access code
            }

            # Run yt-dlp in executor to avoid blocking
            loop = asyncio.get_event_loop()

            def download():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    ydl.download([recording_url])

            await loop.run_in_executor(None, download)

            if os.path.exists(temp_file.name) and os.path.getsize(temp_file.name) > 0:
                logger.info(f"Successfully downloaded with yt-dlp to: {temp_file.name}")
                return temp_file.name
            else:
                os.unlink(temp_file.name)
                return None

        except Exception as e:
            logger.error(f"yt-dlp download failed: {e}")
            try:
                if temp_file and os.path.exists(temp_file.name):
                    os.unlink(temp_file.name)
            except:
                pass
            return None

    async def extract_audio_from_video(self, video_path: str) -> Optional[str]:
        """
        Extract audio track from a video file using ffmpeg.

        Args:
            video_path: Path to the video file

        Returns:
            Path to extracted audio file or None if extraction failed
        """
        try:
            audio_file = tempfile.NamedTemporaryFile(
                delete=False,
                suffix='.mp3',
                dir=tempfile.gettempdir()
            )
            audio_file.close()

            # Use ffmpeg to extract audio
            cmd = [
                'ffmpeg',
                '-i', video_path,
                '-vn',  # No video
                '-acodec', 'libmp3lame',  # MP3 codec
                '-b:a', '192k',  # Audio bitrate
                '-y',  # Overwrite output
                audio_file.name
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode == 0 and os.path.exists(audio_file.name):
                logger.info(f"Successfully extracted audio to: {audio_file.name}")
                return audio_file.name
            else:
                logger.error(f"ffmpeg failed: {stderr.decode()}")
                os.unlink(audio_file.name)
                return None

        except Exception as e:
            logger.error(f"Error extracting audio: {e}")
            return None