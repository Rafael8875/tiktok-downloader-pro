"""
TikTok Downloader Pro - Utility Functions
Video info extraction, downloading, conversion, and file management.
"""
import os
import re
import time
import uuid
import subprocess
import logging
import shutil

import yt_dlp

from app.security import is_ssrf_safe, sanitize_url, sanitize_filename

logger = logging.getLogger(__name__)

# Valid TikTok URL patterns
TIKTOK_PATTERNS = [
    # Standard TikTok video URLs
    r'^https?://(www\.)?tiktok\.com/@[\w.-]+/video/\d+',
    # Short TikTok URLs (vm.tiktok.com, vt.tiktok.com)
    r'^https?://vm\.tiktok\.com/[\w-]+',
    r'^https?://vt\.tiktok\.com/[\w-]+',
    # Mobile TikTok URLs
    r'^https?://m\.tiktok\.com/v/\d+',
    # TikTok with query params
    r'^https?://(www\.)?tiktok\.com/t/[\w-]+',
]


def validate_tiktok_url(url):
    """
    Validate that the URL is a legitimate TikTok URL.
    Also performs SSRF safety check.

    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    if not url:
        return False, "URL não fornecida"

    # Sanitize first
    url = sanitize_url(url)
    if not url:
        return False, "URL inválida ou mal formatada"

    # Check TikTok patterns
    is_tiktok = any(re.match(pattern, url, re.IGNORECASE) for pattern in TIKTOK_PATTERNS)
    if not is_tiktok:
        return False, "URL não é do TikTok. Cole uma URL válida como https://www.tiktok.com/@usuario/video/123..."

    # SSRF protection
    if not is_ssrf_safe(url):
        return False, "URL bloqueada por questões de segurança"

    return True, None


def get_video_info(url):
    """
    Get video information from TikTok without downloading.

    Returns:
        dict: Video metadata including title, duration, thumbnail, formats
    Raises:
        Exception: If video cannot be accessed
    """
    ydl_opts = {
        'quiet': True,
        'no_warnings': True,
        'extract_flat': False,
        'noplaylist': True,
        'socket_timeout': 15,
        # Do NOT use cookies or authentication bypass
        'cookiefile': None,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return info
    except yt_dlp.utils.DownloadError as e:
        error_msg = str(e).lower()
        if any(kw in error_msg for kw in ['private', 'login', 'auth', 'captcha', 'blocked']):
            raise Exception(
                "Este vídeo não está disponível para download. "
                "Pode ser privado, exigir login ou estar protegido contra download."
            )
        raise Exception(f"Erro ao acessar o vídeo: {str(e)}")


def get_available_formats(info):
    """
    Extract available download formats from video info.

    Returns:
        dict with 'video', 'audio', and 'gif' format options
    """
    formats = {
        'video': [],
        'audio': [],
        'gif': False
    }

    # Determine max available height
    available_heights = set()
    for f in info.get('formats', []):
        height = f.get('height')
        if height and f.get('vcodec', 'none') != 'none':
            available_heights.add(height)

    max_height = max(available_heights) if available_heights else 0

    # Standard video qualities (only show what's available)
    quality_map = [
        (360, '360p'),
        (480, '480p'),
        (720, '720p (HD)'),
        (1080, '1080p (Full HD)'),
    ]

    for height, label in quality_map:
        if height <= max_height:
            formats['video'].append({
                'quality': str(height),
                'label': f'MP4 {label}',
                'format': 'mp4'
            })

    # If no specific heights found, offer a "best" option
    if not formats['video'] and info.get('formats'):
        formats['video'].append({
            'quality': 'best',
            'label': 'MP4 (Melhor disponível)',
            'format': 'mp4'
        })

    # Audio formats (always available if video is available)
    if info.get('formats'):
        formats['audio'] = [
            {'quality': '128', 'label': 'MP3 128kbps', 'format': 'mp3'},
            {'quality': '192', 'label': 'MP3 192kbps', 'format': 'mp3'},
            {'quality': '320', 'label': 'MP3 320kbps', 'format': 'mp3'},
        ]

    # GIF is available if video duration is known and reasonable
    duration = info.get('duration', 0)
    if duration and duration > 0:
        formats['gif'] = True

    return formats


def download_video(url, download_dir, quality='720', progress_callback=None):
    """
    Download TikTok video in specified quality.

    Returns:
        str: Path to downloaded file
    """
    file_id = uuid.uuid4().hex[:12]
    output_template = os.path.join(download_dir, f'tiktok_{file_id}.%(ext)s')

    if quality == 'best':
        format_str = 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best'
    else:
        format_str = (
            f'bestvideo[height<={quality}][ext=mp4]+bestaudio[ext=m4a]/'
            f'bestvideo[height<={quality}]+bestaudio/'
            f'best[height<={quality}]/best'
        )

    ydl_opts = {
        'format': format_str,
        'outtmpl': output_template,
        'merge_output_format': 'mp4',
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 3,
        'restrictfilenames': True,
        'postprocessors': [{
            'key': 'FFmpegVideoConvertor',
            'preferedformat': 'mp4',
        }],
    }

    if progress_callback:
        ydl_opts['progress_hooks'] = [progress_callback]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Ensure .mp4 extension
        base = os.path.splitext(filename)[0]
        filename = base + '.mp4'

    if not os.path.exists(filename):
        # Try to find the file with different extension
        for ext in ['.mp4', '.webm', '.mkv']:
            candidate = base + ext
            if os.path.exists(candidate):
                filename = candidate
                break

    if not os.path.exists(filename):
        raise Exception("Arquivo baixado não encontrado. Verifique se o FFmpeg está instalado.")

    return filename


def download_audio(url, download_dir, quality='192', progress_callback=None):
    """
    Download TikTok video and extract audio as MP3.

    Returns:
        str: Path to downloaded MP3 file
    """
    file_id = uuid.uuid4().hex[:12]
    output_template = os.path.join(download_dir, f'tiktok_{file_id}.%(ext)s')

    ydl_opts = {
        'format': 'bestaudio/best',
        'outtmpl': output_template,
        'quiet': True,
        'no_warnings': True,
        'noplaylist': True,
        'socket_timeout': 30,
        'retries': 3,
        'restrictfilenames': True,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': quality,
        }],
    }

    if progress_callback:
        ydl_opts['progress_hooks'] = [progress_callback]

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        filename = ydl.prepare_filename(info)
        # Change extension to mp3
        base = os.path.splitext(filename)[0]
        filename = base + '.mp3'

    if not os.path.exists(filename):
        raise Exception("Arquivo de áudio não encontrado. Verifique se o FFmpeg está instalado.")

    return filename


def create_gif(input_url, output_dir, start_time=0, duration=5, fps=10, width=480):
    """
    Download video and create a GIF from a selected time range.

    Args:
        input_url: TikTok video URL
        output_dir: Directory to save the GIF
        start_time: Start time in seconds
        duration: Duration in seconds (max 10)
        fps: Frames per second (max 15)
        width: Output width in pixels (max 640)

    Returns:
        str: Path to generated GIF file
    """
    # Enforce limits
    duration = min(duration, 10)
    fps = min(fps, 15)
    width = min(width, 640)
    start_time = max(start_time, 0)

    file_id = uuid.uuid4().hex[:12]
    temp_video = os.path.join(output_dir, 'temp', f'gif_source_{file_id}.mp4')
    output_gif = os.path.join(output_dir, f'tiktok_{file_id}.gif')

    try:
        # First download the video
        ydl_opts = {
            'format': 'best[height<=480]/best',
            'outtmpl': temp_video,
            'quiet': True,
            'no_warnings': True,
            'noplaylist': True,
            'socket_timeout': 30,
        }

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.extract_info(input_url, download=True)

        # Find the actual downloaded file
        temp_dir = os.path.join(output_dir, 'temp')
        actual_video = None
        for f in os.listdir(temp_dir):
            if f.startswith(f'gif_source_{file_id}'):
                actual_video = os.path.join(temp_dir, f)
                break

        if not actual_video or not os.path.exists(actual_video):
            raise Exception("Vídeo temporário não encontrado")

        # Use FFmpeg to create GIF
        ffmpeg_cmd = [
            'ffmpeg', '-y',
            '-ss', str(start_time),
            '-t', str(duration),
            '-i', actual_video,
            '-vf', f'fps={fps},scale={width}:-1:flags=lanczos,'
                   f'split[s0][s1];[s0]palettegen[p];[s1][p]paletteuse',
            '-loop', '0',
            output_gif
        ]

        result = subprocess.run(
            ffmpeg_cmd,
            capture_output=True,
            text=True,
            timeout=60
        )

        if result.returncode != 0:
            logger.error("FFmpeg GIF error: %s", result.stderr)
            raise Exception("Erro ao criar GIF. Verifique se o FFmpeg está instalado.")

        return output_gif

    finally:
        # Clean up temp video
        if actual_video and os.path.exists(actual_video):
            try:
                os.remove(actual_video)
            except OSError:
                pass


def cleanup_old_files(download_dir, max_age_minutes=15):
    """
    Remove files older than max_age_minutes.

    Returns:
        int: Number of files removed
    """
    removed = 0
    now = time.time()
    max_age_seconds = max_age_minutes * 60

    try:
        for filename in os.listdir(download_dir):
            filepath = os.path.join(download_dir, filename)
            if os.path.isfile(filepath):
                file_age = now - os.path.getmtime(filepath)
                if file_age > max_age_seconds:
                    try:
                        os.remove(filepath)
                        removed += 1
                    except OSError:
                        pass
    except Exception as e:
        logger.error("Cleanup error: %s", e)

    return removed
