"""Input validation for OmniSight: audio URL fetches and uploaded file names.

Kept free of heavy imports so the server and the tests can use it without
installing the full agent stack.
"""
import ipaddress
import os
import re
import secrets
import socket
import time
from urllib.parse import urljoin, urlsplit

# Uploaded and downloaded audio lives outside the public web root.
AUDIO_DIR = os.environ.get("AUDIO_DIR") or "temp_audio"


def _int_env(name, default):
    try:
        return int(os.environ.get(name) or default)
    except ValueError:
        return default


MAX_AUDIO_BYTES = _int_env("AUDIO_MAX_MB", 50) * 1024 * 1024
MAX_URL_LENGTH = 2048

# Hosts handed to yt-dlp. Anything else is treated as a direct https link.
YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com", "youtu.be"}

ALLOWED_AUDIO_EXTENSIONS = {
    ".mp3", ".wav", ".m4a", ".aac", ".ogg", ".oga", ".opus", ".flac",
    ".webm", ".mp4", ".mpeg", ".mpga", ".amr", ".wma", ".aiff",
}


class UnsafeURLError(ValueError):
    """Raised when a URL must not be fetched by the server."""


def is_public_ip(ip):
    addr = ipaddress.ip_address(ip)
    if isinstance(addr, ipaddress.IPv6Address) and addr.ipv4_mapped:
        addr = addr.ipv4_mapped
    # is_global is False for private, loopback, link-local (incl. 169.254.169.254
    # cloud metadata), CGNAT, unspecified and reserved ranges.
    return addr.is_global and not addr.is_multicast


def validate_public_https_url(url):
    """Check that url is https and that its host resolves only to public IPs.

    Returns (hostname, port, ips). Raises UnsafeURLError otherwise.
    """
    if not isinstance(url, str) or not url.strip() or len(url) > MAX_URL_LENGTH:
        raise UnsafeURLError("URL is missing or too long")
    parts = urlsplit(url.strip())
    if parts.scheme.lower() != "https":
        raise UnsafeURLError("only https URLs are allowed")
    if parts.username or parts.password:
        raise UnsafeURLError("credentials in URLs are not allowed")
    host = parts.hostname
    if not host:
        raise UnsafeURLError("URL has no host")
    try:
        port = parts.port or 443
    except ValueError:
        raise UnsafeURLError("invalid port")
    try:
        infos = socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)
    except (socket.gaierror, UnicodeError):
        raise UnsafeURLError("host does not resolve")
    ips = sorted({info[4][0] for info in infos})
    if not ips or not all(is_public_ip(ip) for ip in ips):
        raise UnsafeURLError("host resolves to a private, loopback, link-local or reserved address")
    return host, port, ips


def is_youtube_url(url):
    try:
        parts = urlsplit(url.strip())
    except (AttributeError, ValueError):
        return False
    return parts.scheme.lower() == "https" and (parts.hostname or "") in YOUTUBE_HOSTS


def download_public_https(url, dest_path, max_bytes=MAX_AUDIO_BYTES, timeout=30.0, max_redirects=5, transport=None):
    """Stream an https URL to dest_path without reaching internal addresses.

    Every redirect hop is re-validated, and the connection is pinned to the
    address that was checked (TLS still verifies the original host name), so a
    DNS answer cannot change between the check and the request.
    """
    import httpx

    current = url
    for _ in range(max_redirects + 1):
        host, port, ips = validate_public_https_url(current)
        parts = urlsplit(current.strip())
        ip = ips[0]
        ip_host = f"[{ip}]" if ":" in ip else ip
        pinned_url = parts._replace(netloc=f"{ip_host}:{port}").geturl()
        with httpx.Client(follow_redirects=False, timeout=timeout, transport=transport) as client:
            request_kwargs = {"headers": {"Host": parts.netloc}, "extensions": {"sni_hostname": host}}
            with client.stream("GET", pinned_url, **request_kwargs) as r:
                if r.is_redirect:
                    current = urljoin(current, r.headers["location"])
                    continue
                r.raise_for_status()
                declared = r.headers.get("content-length")
                if declared and declared.isdigit() and int(declared) > max_bytes:
                    raise UnsafeURLError("download exceeds the size limit")
                written = 0
                try:
                    with open(dest_path, "wb") as f:
                        for chunk in r.iter_bytes():
                            written += len(chunk)
                            if written > max_bytes:
                                raise UnsafeURLError("download exceeds the size limit")
                            f.write(chunk)
                except Exception:
                    if os.path.exists(dest_path):
                        os.remove(dest_path)
                    raise
                return dest_path
    raise UnsafeURLError("too many redirects")


def safe_upload_name(filename):
    """Build a server-side file name from a client-supplied one.

    Only a short, sanitised stem of the original name survives; the extension
    must be a known audio type. Directory parts are always dropped.
    """
    base = re.split(r"[\\/]", str(filename or ""))[-1]
    stem, ext = os.path.splitext(base)
    ext = ext.lower()
    if ext not in ALLOWED_AUDIO_EXTENSIONS:
        ext = ".audio"
    stem = re.sub(r"[^A-Za-z0-9_-]", "_", stem).strip("_")[:40] or "upload"
    return f"{int(time.time())}_{secrets.token_hex(4)}_{stem}{ext}"


def confined_path(base_dir, name):
    """Join name onto base_dir and refuse anything that resolves outside it."""
    base = os.path.realpath(base_dir)
    path = os.path.realpath(os.path.join(base, name))
    if os.path.commonpath([base, path]) != base or path == base:
        raise ValueError("path escapes the upload directory")
    return path
