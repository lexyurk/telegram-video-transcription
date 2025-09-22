"""Service for extracting media file information."""

import asyncio
import json
from pathlib import Path
from typing import Optional, Dict, Any
from loguru import logger


class MediaInfoService:
    """Service for extracting metadata from media files using ffprobe."""

    async def get_media_duration(self, file_path: str) -> Optional[float]:
        """
        Extract duration in seconds from a media file using ffprobe.

        Args:
            file_path: Path to the media file

        Returns:
            Duration in seconds or None if extraction fails
        """
        try:
            # Run ffprobe command to get duration
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.warning(f"ffprobe failed with return code {process.returncode}")
                if stderr:
                    logger.debug(f"ffprobe stderr: {stderr.decode()}")
                return None

            # Parse JSON output
            data = json.loads(stdout.decode())

            # Try to get duration from format first
            if 'format' in data and 'duration' in data['format']:
                duration = float(data['format']['duration'])
                logger.info(f"Extracted duration from format: {duration:.2f} seconds")
                return duration

            # Fallback to stream duration
            if 'streams' in data:
                for stream in data['streams']:
                    if 'duration' in stream:
                        duration = float(stream['duration'])
                        logger.info(f"Extracted duration from stream: {duration:.2f} seconds")
                        return duration

            logger.warning("No duration found in media file metadata")
            return None

        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse ffprobe JSON output: {e}")
            return None
        except Exception as e:
            logger.error(f"Error extracting media duration: {e}")
            return None

    async def get_media_info(self, file_path: str) -> Dict[str, Any]:
        """
        Extract comprehensive media information from a file.

        Args:
            file_path: Path to the media file

        Returns:
            Dictionary with media information
        """
        info = {
            'duration_seconds': None,
            'duration_minutes': None,
            'format': None,
            'codec': None,
            'bitrate': None,
            'sample_rate': None,
            'channels': None,
            'has_video': False,
            'has_audio': False,
            'width': None,
            'height': None,
            'fps': None
        }

        try:
            cmd = [
                'ffprobe',
                '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                str(file_path)
            ]

            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            stdout, stderr = await process.communicate()

            if process.returncode != 0:
                logger.warning(f"ffprobe failed with return code {process.returncode}")
                return info

            data = json.loads(stdout.decode())

            # Extract format info
            if 'format' in data:
                fmt = data['format']
                if 'duration' in fmt:
                    info['duration_seconds'] = float(fmt['duration'])
                    info['duration_minutes'] = info['duration_seconds'] / 60.0
                if 'format_name' in fmt:
                    info['format'] = fmt['format_name']
                if 'bit_rate' in fmt:
                    info['bitrate'] = int(fmt['bit_rate'])

            # Extract stream info
            if 'streams' in data:
                for stream in data['streams']:
                    codec_type = stream.get('codec_type')

                    if codec_type == 'audio':
                        info['has_audio'] = True
                        if not info['codec']:
                            info['codec'] = stream.get('codec_name')
                        if 'sample_rate' in stream:
                            info['sample_rate'] = int(stream['sample_rate'])
                        if 'channels' in stream:
                            info['channels'] = stream['channels']

                    elif codec_type == 'video':
                        info['has_video'] = True
                        if 'width' in stream:
                            info['width'] = stream['width']
                        if 'height' in stream:
                            info['height'] = stream['height']
                        if 'r_frame_rate' in stream:
                            # Parse frame rate (e.g., "30/1" -> 30.0)
                            rate = stream['r_frame_rate']
                            if '/' in rate:
                                num, den = rate.split('/')
                                if den != '0':
                                    info['fps'] = float(num) / float(den)

            logger.info(f"Extracted media info: duration={info['duration_minutes']:.2f} min, "
                       f"format={info['format']}, has_video={info['has_video']}, "
                       f"has_audio={info['has_audio']}")

        except Exception as e:
            logger.error(f"Error extracting media info: {e}")

        return info