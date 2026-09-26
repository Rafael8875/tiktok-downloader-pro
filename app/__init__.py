"""
TikTok Downloader Pro - Flask Application Factory
"""
import os
import time
import threading
import logging

from flask import Flask
from dotenv import load_dotenv

load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Global concurrency semaphore (max 3 simultaneous downloads)
download_semaphore = threading.Semaphore(3)

# In-memory task storage
tasks = {}

# Stats counter
stats = {
    'total_downloads': 0,
    'total_analyses': 0,
    'total_gifs': 0
}


def create_app():
    """Create and configure the Flask application."""
    app = Flask(__name__)

    # --- Configuration ---
    app.config['SECRET_KEY'] = os.environ.get(
        'SECRET_KEY', 'dev-secret-key-change-in-production'
    )
    app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max

    # Download directory (Render uses persistent disk)
    if os.environ.get('RENDER'):
        app.config['DOWNLOAD_DIR'] = '/opt/render/project/downloads'
    else:
        app.config['DOWNLOAD_DIR'] = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'downloads'
        )

    # Temp directory for intermediate files
    app.config['TEMP_DIR'] = os.path.join(app.config['DOWNLOAD_DIR'], 'temp')

    os.makedirs(app.config['DOWNLOAD_DIR'], exist_ok=True)
    os.makedirs(app.config['TEMP_DIR'], exist_ok=True)

    # File expiration (seconds)
    app.config['FILE_EXPIRATION'] = int(
        os.environ.get('FILE_EXPIRATION', 900)  # 15 minutes default
    )

    # Max file size for downloads (bytes)
    app.config['MAX_DOWNLOAD_SIZE'] = 100 * 1024 * 1024  # 100MB

    # --- Rate Limiting ---
    try:
        from flask_limiter import Limiter
        from flask_limiter.util import get_remote_address

        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per hour"],
            storage_uri="memory://",
        )
        app.limiter = limiter
    except ImportError:
        logger.warning("flask-limiter not installed, rate limiting disabled")
        app.limiter = None

    # --- Register Routes ---
    from app.routes import main_bp
    app.register_blueprint(main_bp)

    # Apply rate limits if limiter is available
    if app.limiter:
        app.limiter.limit("30 per hour")(
            app.view_functions.get('main.analyze', lambda: None)
        )
        app.limiter.limit("20 per hour")(
            app.view_functions.get('main.start_download', lambda: None)
        )
        app.limiter.limit("10 per hour")(
            app.view_functions.get('main.create_gif', lambda: None)
        )

    # --- Start Cleanup Thread ---
    cleanup_thread = threading.Thread(
        target=_cleanup_loop,
        args=(app.config['DOWNLOAD_DIR'], app.config['FILE_EXPIRATION']),
        daemon=True
    )
    cleanup_thread.start()
    logger.info("File cleanup thread started (interval: %ds)", app.config['FILE_EXPIRATION'])

    logger.info("TikTok Downloader Pro initialized successfully")
    return app


def _cleanup_loop(download_dir, max_age_seconds):
    """Background thread that removes expired files periodically."""
    while True:
        time.sleep(300)  # Check every 5 minutes
        try:
            now = time.time()
            removed = 0
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

            # Also clean temp directory
            temp_dir = os.path.join(download_dir, 'temp')
            if os.path.isdir(temp_dir):
                for filename in os.listdir(temp_dir):
                    filepath = os.path.join(temp_dir, filename)
                    if os.path.isfile(filepath):
                        file_age = now - os.path.getmtime(filepath)
                        if file_age > max_age_seconds:
                            try:
                                os.remove(filepath)
                                removed += 1
                            except OSError:
                                pass

            if removed > 0:
                logger.info("Cleanup: removed %d expired file(s)", removed)
        except Exception as e:
            logger.error("Cleanup error: %s", e)
