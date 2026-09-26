"""
TikTok Downloader Pro - API Routes
All HTTP endpoints for the application.
"""
import os
import uuid
import time
import threading
import logging

from flask import (
    Blueprint, render_template, request, jsonify,
    send_file, current_app
)

from app.utils import (
    validate_tiktok_url,
    get_video_info,
    get_available_formats,
    download_video,
    download_audio,
    create_gif,
    cleanup_old_files,
)
from app.security import sanitize_filename

logger = logging.getLogger(__name__)

main_bp = Blueprint('main', __name__)


@main_bp.route('/')
def index():
    """Serve the frontend."""
    return render_template('index.html')


@main_bp.route('/api/health')
def health():
    """Health check endpoint for Render."""
    import shutil
    ffmpeg_ok = shutil.which('ffmpeg') is not None
    return jsonify({
        'status': 'ok',
        'ffmpeg': ffmpeg_ok,
        'timestamp': time.time()
    })


@main_bp.route('/api/analyze', methods=['POST'])
def analyze():
    """Analyze a TikTok URL and return video metadata + available formats."""
    from app import stats

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados não fornecidos'}), 400

    url = data.get('url', '').strip()

    # Validate URL
    is_valid, error_msg = validate_tiktok_url(url)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    try:
        info = get_video_info(url)
        stats['total_analyses'] += 1

        formats = get_available_formats(info)

        # Build response
        duration = info.get('duration', 0)
        if duration:
            mins, secs = divmod(int(duration), 60)
            duration_str = f"{mins}:{secs:02d}"
        else:
            duration_str = "Desconhecida"

        return jsonify({
            'success': True,
            'video': {
                'title': info.get('title', info.get('description', 'Vídeo do TikTok'))[:150],
                'duration': duration,
                'duration_str': duration_str,
                'thumbnail': info.get('thumbnail', ''),
                'channel': info.get('uploader', info.get('creator', 'TikTok')),
                'views': info.get('view_count', 0),
                'like_count': info.get('like_count', 0),
            },
            'formats': formats,
            'download_available': len(formats['video']) > 0 or len(formats['audio']) > 0
        })

    except Exception as e:
        error_str = str(e)
        logger.error("Analysis error: %s", error_str)

        # Check if it's a "not available" error
        not_available_keywords = ['privado', 'private', 'login', 'captcha', 'blocked', 'indisponível']
        is_unavailable = any(kw in error_str.lower() for kw in not_available_keywords)

        return jsonify({
            'error': error_str,
            'unavailable': is_unavailable,
            'tiktok_url': url if is_unavailable else None
        }), 400 if is_unavailable else 500


@main_bp.route('/api/download', methods=['POST'])
def start_download():
    """Start a download task in a background thread."""
    from app import tasks, stats, download_semaphore

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados não fornecidos'}), 400

    url = data.get('url', '').strip()
    format_type = data.get('format', 'mp4')
    quality = data.get('quality', '720')

    # Validate URL
    is_valid, error_msg = validate_tiktok_url(url)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    # Validate format
    if format_type not in ('mp4', 'mp3'):
        return jsonify({'error': 'Formato inválido. Use mp4 ou mp3.'}), 400

    # Validate quality
    valid_video_qualities = ['360', '480', '720', '1080', 'best']
    valid_audio_qualities = ['128', '192', '320']

    if format_type == 'mp4' and quality not in valid_video_qualities:
        quality = '720'
    elif format_type == 'mp3' and quality not in valid_audio_qualities:
        quality = '192'

    # Create task
    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'queued',
        'progress': 0,
        'filename': None,
        'error': None,
        'created_at': time.time()
    }

    # Run download in background thread
    thread = threading.Thread(
        target=_process_download,
        args=(task_id, url, format_type, quality),
        daemon=True
    )
    thread.start()

    return jsonify({'task_id': task_id})


def _process_download(task_id, url, format_type, quality):
    """Process download in background thread with concurrency control."""
    from app import create_app, tasks, stats, download_semaphore

    app = create_app()

    with app.app_context():
        # Wait for semaphore (max 3 concurrent downloads)
        acquired = download_semaphore.acquire(timeout=60)
        if not acquired:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = 'Servidor ocupado. Tente novamente em alguns instantes.'
            return

        try:
            tasks[task_id]['status'] = 'downloading'
            download_dir = app.config['DOWNLOAD_DIR']

            def progress_callback(d):
                if d['status'] == 'downloading':
                    total = d.get('total_bytes') or d.get('total_bytes_estimate', 0)
                    downloaded = d.get('downloaded_bytes', 0)
                    speed = d.get('speed', 0)

                    if total > 0:
                        # Check file size limit
                        max_size = app.config.get('MAX_DOWNLOAD_SIZE', 100 * 1024 * 1024)
                        if total > max_size:
                            raise Exception(
                                f"Arquivo muito grande ({total // (1024*1024)}MB). "
                                f"Limite: {max_size // (1024*1024)}MB."
                            )
                        tasks[task_id]['progress'] = min(95, int((downloaded / total) * 100))
                    else:
                        # Estimate progress based on downloaded bytes
                        tasks[task_id]['progress'] = min(50, downloaded // (1024 * 1024))

                    if speed:
                        tasks[task_id]['speed'] = f"{speed / (1024*1024):.1f} MB/s"

                elif d['status'] == 'finished':
                    tasks[task_id]['progress'] = 95
                    tasks[task_id]['status'] = 'processing'

            if format_type == 'mp3':
                filename = download_audio(url, download_dir, quality, progress_callback)
            else:
                filename = download_video(url, download_dir, quality, progress_callback)

            tasks[task_id]['status'] = 'completed'
            tasks[task_id]['progress'] = 100
            tasks[task_id]['filename'] = filename
            stats['total_downloads'] += 1

            logger.info("Download completed: %s (%s %s)", task_id, format_type, quality)

        except Exception as e:
            tasks[task_id]['status'] = 'error'
            tasks[task_id]['error'] = str(e)
            logger.error("Download error [%s]: %s", task_id, e)

        finally:
            download_semaphore.release()


@main_bp.route('/api/progress/<task_id>')
def get_progress(task_id):
    """Get the progress of a download task."""
    from app import tasks

    task = tasks.get(task_id)
    if not task:
        return jsonify({'error': 'Tarefa não encontrada'}), 404

    return jsonify(task)


@main_bp.route('/api/file/<task_id>')
def download_file(task_id):
    """Serve a completed download file."""
    from app import tasks

    task = tasks.get(task_id)
    if not task or task.get('status') != 'completed':
        return jsonify({'error': 'Download não disponível'}), 404

    filepath = task.get('filename')
    if not filepath or not os.path.exists(filepath):
        return jsonify({'error': 'Arquivo não encontrado ou expirado'}), 404

    filename = os.path.basename(filepath)

    # Schedule cleanup after 10 minutes
    def delayed_cleanup():
        time.sleep(600)
        try:
            if os.path.exists(filepath):
                os.remove(filepath)
            if task_id in tasks:
                del tasks[task_id]
        except Exception:
            pass

    cleanup_thread = threading.Thread(target=delayed_cleanup, daemon=True)
    cleanup_thread.start()

    return send_file(filepath, as_attachment=True, download_name=filename)


@main_bp.route('/api/gif', methods=['POST'])
def create_gif_endpoint():
    """Create a GIF from a TikTok video."""
    from app import tasks, stats

    data = request.get_json()
    if not data:
        return jsonify({'error': 'Dados não fornecidos'}), 400

    url = data.get('url', '').strip()
    start_time = data.get('start', 0)
    duration = data.get('duration', 5)

    # Validate URL
    is_valid, error_msg = validate_tiktok_url(url)
    if not is_valid:
        return jsonify({'error': error_msg}), 400

    # Validate parameters
    try:
        start_time = max(0, float(start_time))
        duration = max(1, min(10, float(duration)))
    except (ValueError, TypeError):
        return jsonify({'error': 'Parâmetros de tempo inválidos'}), 400

    task_id = str(uuid.uuid4())
    tasks[task_id] = {
        'status': 'processing',
        'progress': 50,
        'filename': None,
        'error': None,
        'created_at': time.time()
    }

    # Run in background
    def process_gif():
        from app import create_app, download_semaphore

        app = create_app()
        with app.app_context():
            acquired = download_semaphore.acquire(timeout=60)
            if not acquired:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = 'Servidor ocupado'
                return

            try:
                download_dir = app.config['DOWNLOAD_DIR']
                gif_path = create_gif(url, download_dir, start_time, duration)

                tasks[task_id]['status'] = 'completed'
                tasks[task_id]['progress'] = 100
                tasks[task_id]['filename'] = gif_path
                stats['total_gifs'] += 1

            except Exception as e:
                tasks[task_id]['status'] = 'error'
                tasks[task_id]['error'] = str(e)
                logger.error("GIF error [%s]: %s", task_id, e)
            finally:
                download_semaphore.release()

    threading.Thread(target=process_gif, daemon=True).start()

    return jsonify({'task_id': task_id})


@main_bp.route('/api/stats')
def get_stats():
    """Return usage statistics."""
    from app import stats
    return jsonify(stats)


@main_bp.route('/api/cleanup', methods=['POST'])
def trigger_cleanup():
    """Manually trigger file cleanup."""
    download_dir = current_app.config['DOWNLOAD_DIR']
    removed = cleanup_old_files(download_dir, max_age_minutes=15)
    return jsonify({'removed': removed})
