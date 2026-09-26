"""
TikTok Downloader Pro - Security Module
SSRF protection, URL sanitization, and input validation.
"""
import re
import ipaddress
import socket
import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)

# Private/reserved IP ranges that should be blocked
BLOCKED_IP_RANGES = [
    ipaddress.ip_network('127.0.0.0/8'),       # Loopback
    ipaddress.ip_network('10.0.0.0/8'),         # Private
    ipaddress.ip_network('172.16.0.0/12'),      # Private
    ipaddress.ip_network('192.168.0.0/16'),     # Private
    ipaddress.ip_network('169.254.0.0/16'),     # Link-local
    ipaddress.ip_network('0.0.0.0/8'),          # Current network
    ipaddress.ip_network('100.64.0.0/10'),      # Shared address space
    ipaddress.ip_network('198.18.0.0/15'),      # Benchmarking
    ipaddress.ip_network('::1/128'),            # IPv6 loopback
    ipaddress.ip_network('fc00::/7'),           # IPv6 private
    ipaddress.ip_network('fe80::/10'),          # IPv6 link-local
]


def is_ip_safe(ip_str):
    """Check if an IP address is safe (not private/reserved)."""
    try:
        ip = ipaddress.ip_address(ip_str)
        for network in BLOCKED_IP_RANGES:
            if ip in network:
                return False
        return True
    except ValueError:
        return False


def is_ssrf_safe(url):
    """
    Check if a URL is safe from SSRF attacks.
    Resolves the hostname and checks if it points to a private IP.
    """
    try:
        parsed = urlparse(url)
        hostname = parsed.hostname

        if not hostname:
            return False

        # Block obvious localhost references
        if hostname in ('localhost', '0.0.0.0', '[::]', '[::1]'):
            return False

        # Block IP addresses directly in URL
        try:
            ip = ipaddress.ip_address(hostname)
            return is_ip_safe(str(ip))
        except ValueError:
            pass  # It's a hostname, not an IP — continue to DNS resolution

        # Resolve hostname and check all IPs
        try:
            addr_infos = socket.getaddrinfo(hostname, None, socket.AF_UNSPEC)
            for addr_info in addr_infos:
                ip_str = addr_info[4][0]
                if not is_ip_safe(ip_str):
                    logger.warning(
                        "SSRF blocked: %s resolves to private IP %s",
                        hostname, ip_str
                    )
                    return False
        except socket.gaierror:
            # DNS resolution failed — could be a valid TikTok URL on a
            # network that blocks DNS, so we allow it (yt-dlp will handle)
            pass

        return True
    except Exception as e:
        logger.error("SSRF check error: %s", e)
        return False


def sanitize_url(url):
    """
    Sanitize a URL by removing fragments, normalizing scheme,
    and stripping dangerous characters.
    """
    if not url or not isinstance(url, str):
        return None

    url = url.strip()

    # Must start with http:// or https://
    if not url.startswith(('http://', 'https://')):
        return None

    try:
        parsed = urlparse(url)

        # Reconstruct without fragment
        sanitized = urlunparse((
            parsed.scheme,
            parsed.netloc,
            parsed.path,
            parsed.params,
            parsed.query,
            ''  # Remove fragment
        ))

        return sanitized
    except Exception:
        return None


def sanitize_filename(name):
    """
    Remove dangerous characters from a filename to prevent
    path traversal and filesystem issues.
    """
    if not name:
        return 'download'

    # Remove path separators and null bytes
    name = name.replace('/', '_').replace('\\', '_').replace('\x00', '')

    # Remove path traversal sequences
    while '..' in name:
        name = name.replace('..', '')

    # Remove or replace special characters
    name = re.sub(r'[<>:"|?*]', '', name)

    # Limit length
    name = name[:200]

    # Remove leading/trailing dots and spaces
    name = name.strip('. ')

    return name if name else 'download'


def validate_content_type(content_type, allowed_types):
    """Validate that a Content-Type header matches allowed types."""
    if not content_type:
        return False
    # Get just the mime type, ignore parameters
    mime_type = content_type.split(';')[0].strip().lower()
    return mime_type in allowed_types
