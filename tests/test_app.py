"""
TikTok Downloader Pro - Automated Tests
Tests for URL validation, security, API endpoints, and utilities.
"""
import os
import sys
import json
import pytest

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import create_app
from app.security import (
    is_ip_safe,
    is_ssrf_safe,
    sanitize_url,
    sanitize_filename,
)
from app.utils import validate_tiktok_url


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def app():
    """Create a test Flask application."""
    os.environ['SECRET_KEY'] = 'test-secret-key'
    os.environ['FLASK_DEBUG'] = 'false'
    application = create_app()
    application.config['TESTING'] = True
    return application


@pytest.fixture
def client(app):
    """Create a test client."""
    return app.test_client()


# ============================================================
# URL Validation Tests
# ============================================================

class TestTikTokURLValidation:
    """Tests for TikTok URL validation."""

    def test_valid_standard_url(self):
        is_valid, error = validate_tiktok_url(
            'https://www.tiktok.com/@user/video/1234567890123456789'
        )
        assert is_valid is True
        assert error is None

    def test_valid_short_url_vm(self):
        is_valid, error = validate_tiktok_url(
            'https://vm.tiktok.com/ZMrAbCdEf'
        )
        assert is_valid is True
        assert error is None

    def test_valid_short_url_vt(self):
        is_valid, error = validate_tiktok_url(
            'https://vt.tiktok.com/ZSrAbCdEf/'
        )
        assert is_valid is True
        assert error is None

    def test_valid_mobile_url(self):
        is_valid, error = validate_tiktok_url(
            'https://m.tiktok.com/v/1234567890'
        )
        assert is_valid is True
        assert error is None

    def test_valid_t_url(self):
        is_valid, error = validate_tiktok_url(
            'https://www.tiktok.com/t/ZTRAbCdEf'
        )
        assert is_valid is True
        assert error is None

    def test_invalid_empty_url(self):
        is_valid, error = validate_tiktok_url('')
        assert is_valid is False
        assert error is not None

    def test_invalid_none_url(self):
        is_valid, error = validate_tiktok_url(None)
        assert is_valid is False

    def test_invalid_youtube_url(self):
        is_valid, error = validate_tiktok_url(
            'https://www.youtube.com/watch?v=dQw4w9WgXcQ'
        )
        assert is_valid is False
        assert 'TikTok' in error

    def test_invalid_instagram_url(self):
        is_valid, error = validate_tiktok_url(
            'https://www.instagram.com/reel/ABC123'
        )
        assert is_valid is False

    def test_invalid_random_url(self):
        is_valid, error = validate_tiktok_url(
            'https://example.com/some/path'
        )
        assert is_valid is False

    def test_invalid_javascript_url(self):
        is_valid, error = validate_tiktok_url('javascript:alert(1)')
        assert is_valid is False

    def test_invalid_ftp_url(self):
        is_valid, error = validate_tiktok_url(
            'ftp://tiktok.com/@user/video/123'
        )
        assert is_valid is False


# ============================================================
# Security Tests
# ============================================================

class TestSSRFProtection:
    """Tests for SSRF protection."""

    def test_localhost_blocked(self):
        assert is_ssrf_safe('http://localhost/evil') is False

    def test_loopback_ip_blocked(self):
        assert is_ip_safe('127.0.0.1') is False

    def test_private_ip_10_blocked(self):
        assert is_ip_safe('10.0.0.1') is False

    def test_private_ip_172_blocked(self):
        assert is_ip_safe('172.16.0.1') is False

    def test_private_ip_192_blocked(self):
        assert is_ip_safe('192.168.1.1') is False

    def test_link_local_blocked(self):
        assert is_ip_safe('169.254.1.1') is False

    def test_public_ip_allowed(self):
        assert is_ip_safe('8.8.8.8') is True

    def test_public_ip_allowed_2(self):
        assert is_ip_safe('1.1.1.1') is True

    def test_ipv6_loopback_blocked(self):
        assert is_ip_safe('::1') is False

    def test_zero_ip_blocked(self):
        assert is_ssrf_safe('http://0.0.0.0/evil') is False

    def test_tiktok_domain_allowed(self):
        assert is_ssrf_safe('https://www.tiktok.com/@user/video/123') is True


class TestURLSanitization:
    """Tests for URL sanitization."""

    def test_strip_whitespace(self):
        result = sanitize_url('  https://www.tiktok.com/test  ')
        assert result == 'https://www.tiktok.com/test'

    def test_remove_fragment(self):
        result = sanitize_url('https://www.tiktok.com/test#fragment')
        assert '#' not in result

    def test_reject_no_scheme(self):
        result = sanitize_url('www.tiktok.com/test')
        assert result is None

    def test_reject_none(self):
        result = sanitize_url(None)
        assert result is None

    def test_reject_empty(self):
        result = sanitize_url('')
        assert result is None

    def test_accept_https(self):
        result = sanitize_url('https://www.tiktok.com/test')
        assert result is not None


class TestFilenameSanitization:
    """Tests for filename sanitization."""

    def test_remove_path_traversal(self):
        result = sanitize_filename('../../../etc/passwd')
        assert '..' not in result
        assert '/' not in result

    def test_remove_special_chars(self):
        result = sanitize_filename('video<>:"|?*.mp4')
        assert '<' not in result
        assert '>' not in result
        assert ':' not in result

    def test_limit_length(self):
        long_name = 'a' * 300 + '.mp4'
        result = sanitize_filename(long_name)
        assert len(result) <= 200

    def test_empty_returns_default(self):
        result = sanitize_filename('')
        assert result == 'download'

    def test_none_returns_default(self):
        result = sanitize_filename(None)
        assert result == 'download'

    def test_normal_filename_unchanged(self):
        result = sanitize_filename('my_video.mp4')
        assert result == 'my_video.mp4'


# ============================================================
# API Endpoint Tests
# ============================================================

class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_returns_200(self, client):
        response = client.get('/api/health')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert data['status'] == 'ok'
        assert 'ffmpeg' in data
        assert 'timestamp' in data


class TestAnalyzeEndpoint:
    """Tests for the analyze endpoint."""

    def test_analyze_no_data(self, client):
        response = client.post('/api/analyze',
                               content_type='application/json',
                               data=json.dumps({}))
        assert response.status_code == 400

    def test_analyze_empty_url(self, client):
        response = client.post('/api/analyze',
                               content_type='application/json',
                               data=json.dumps({'url': ''}))
        assert response.status_code == 400

    def test_analyze_invalid_url(self, client):
        response = client.post('/api/analyze',
                               content_type='application/json',
                               data=json.dumps({'url': 'https://youtube.com/watch?v=abc'}))
        assert response.status_code == 400
        data = json.loads(response.data)
        assert 'error' in data

    def test_analyze_non_json(self, client):
        response = client.post('/api/analyze', data='not json')
        # Flask 3.x returns 415 for non-JSON content type
        assert response.status_code in (400, 415)


class TestDownloadEndpoint:
    """Tests for the download endpoint."""

    def test_download_no_data(self, client):
        response = client.post('/api/download',
                               content_type='application/json',
                               data=json.dumps({}))
        assert response.status_code == 400

    def test_download_invalid_url(self, client):
        response = client.post('/api/download',
                               content_type='application/json',
                               data=json.dumps({
                                   'url': 'https://evil.com/hack',
                                   'format': 'mp4',
                                   'quality': '720'
                               }))
        assert response.status_code == 400

    def test_download_invalid_format(self, client):
        response = client.post('/api/download',
                               content_type='application/json',
                               data=json.dumps({
                                   'url': 'https://www.tiktok.com/@user/video/123',
                                   'format': 'exe',
                                   'quality': '720'
                               }))
        assert response.status_code == 400


class TestProgressEndpoint:
    """Tests for the progress endpoint."""

    def test_progress_invalid_task(self, client):
        response = client.get('/api/progress/nonexistent-task-id')
        assert response.status_code == 404


class TestStatsEndpoint:
    """Tests for the stats endpoint."""

    def test_stats_returns_200(self, client):
        response = client.get('/api/stats')
        assert response.status_code == 200
        data = json.loads(response.data)
        assert 'total_downloads' in data
        assert 'total_analyses' in data


class TestIndexEndpoint:
    """Tests for the frontend endpoint."""

    def test_index_returns_200(self, client):
        response = client.get('/')
        assert response.status_code == 200
        assert b'TikTok Downloader' in response.data


# ============================================================
# Run tests
# ============================================================

if __name__ == '__main__':
    pytest.main([__file__, '-v'])
