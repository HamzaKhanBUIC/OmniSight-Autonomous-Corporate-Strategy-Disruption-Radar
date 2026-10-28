import os
import re
import socket

import httpx
import pytest

import security_utils
from security_utils import (
    UnsafeURLError,
    confined_path,
    download_public_https,
    is_youtube_url,
    safe_upload_name,
    validate_public_https_url,
)


def fake_dns(monkeypatch, table):
    """Resolve host names from table instead of the network."""

    def getaddrinfo(host, port, *args, **kwargs):
        if host not in table:
            raise socket.gaierror("no such host")
        return [(socket.AF_INET6 if ":" in ip else socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))
                for ip in table[host]]

    monkeypatch.setattr(security_utils.socket, "getaddrinfo", getaddrinfo)


# --- SSRF validator -----------------------------------------------------------

@pytest.mark.parametrize("url", [
    "http://example.com/a.mp3",
    "ftp://example.com/a.mp3",
    "file:///etc/passwd",
    "gopher://127.0.0.1:6379/_INFO",
    "https://",
    "https:///no-host",
    "https://user:pass@example.com/a.mp3",
    "https://example.com:99999/a.mp3",
    "https://example.com/" + "a" * 3000,
    "",
    None,
    ["https://example.com"],
])
def test_rejects_bad_scheme_or_shape(url):
    with pytest.raises(UnsafeURLError):
        validate_public_https_url(url)


@pytest.mark.parametrize("ip", [
    "127.0.0.1",
    "10.0.0.5",
    "172.16.0.1",
    "192.168.1.10",
    "169.254.169.254",   # cloud metadata
    "100.64.0.1",        # CGNAT
    "0.0.0.0",
    "224.0.0.1",
    "::1",
    "fe80::1",
    "fd00:ec2::254",     # AWS IPv6 metadata
    "::ffff:127.0.0.1",  # IPv4-mapped loopback
])
def test_rejects_hosts_resolving_to_internal_addresses(monkeypatch, ip):
    fake_dns(monkeypatch, {"audio.example": [ip]})
    with pytest.raises(UnsafeURLError):
        validate_public_https_url("https://audio.example/clip.mp3")


@pytest.mark.parametrize("url", [
    "https://127.0.0.1/clip.mp3",
    "https://[::1]/clip.mp3",
    "https://169.254.169.254/latest/meta-data/",
    "https://localhost/clip.mp3",
])
def test_rejects_internal_literals(url):
    # IP literals and localhost resolve locally, no network needed
    with pytest.raises(UnsafeURLError):
        validate_public_https_url(url)


def test_rejects_when_any_resolved_address_is_internal(monkeypatch):
    fake_dns(monkeypatch, {"rebind.example": ["93.184.216.34", "10.0.0.1"]})
    with pytest.raises(UnsafeURLError):
        validate_public_https_url("https://rebind.example/a.mp3")


def test_rejects_unresolvable_host(monkeypatch):
    fake_dns(monkeypatch, {})
    with pytest.raises(UnsafeURLError):
        validate_public_https_url("https://nope.example/a.mp3")


def test_accepts_public_https(monkeypatch):
    fake_dns(monkeypatch, {"cdn.example": ["93.184.216.34"]})
    assert validate_public_https_url("https://cdn.example/a.mp3") == ("cdn.example", 443, ["93.184.216.34"])
    assert validate_public_https_url("https://CDN.example:8443/a.mp3")[:2] == ("cdn.example", 8443)


@pytest.mark.parametrize("url,expected", [
    ("https://www.youtube.com/watch?v=03Q0IVpRBAA", True),
    ("https://youtu.be/03Q0IVpRBAA", True),
    ("https://m.youtube.com/watch?v=x", True),
    ("http://www.youtube.com/watch?v=x", False),
    ("https://evil.example/?u=youtube.com", False),
    ("https://youtube.com.evil.example/watch", False),
    ("https://notyoutu.be/x", False),
])
def test_youtube_detection_uses_parsed_host(url, expected):
    assert is_youtube_url(url) is expected


# --- pinned download ----------------------------------------------------------

def test_download_is_pinned_to_checked_ip(monkeypatch, tmp_path):
    fake_dns(monkeypatch, {"files.example": ["93.184.216.34"]})
    seen = []

    def handler(request):
        seen.append(request)
        return httpx.Response(200, content=b"RIFFdata")

    dest = tmp_path / "a.media"
    download_public_https("https://files.example/a.wav", str(dest), transport=httpx.MockTransport(handler))

    assert dest.read_bytes() == b"RIFFdata"
    (req,) = seen
    assert req.url.host == "93.184.216.34"
    assert req.headers["host"] == "files.example"
    assert req.extensions["sni_hostname"] == "files.example"


@pytest.mark.parametrize("location", [
    "https://internal.example/secret",
    "http://files.example/a.wav",
    "https://169.254.169.254/latest/meta-data/",
])
def test_download_revalidates_redirects(monkeypatch, tmp_path, location):
    fake_dns(monkeypatch, {"files.example": ["93.184.216.34"], "internal.example": ["10.0.0.7"]})
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": location})

    with pytest.raises(UnsafeURLError):
        download_public_https("https://files.example/a.wav", str(tmp_path / "a.media"),
                              transport=httpx.MockTransport(handler))
    assert len(calls) == 1  # the internal target was never requested


def test_download_enforces_size_limit(monkeypatch, tmp_path):
    fake_dns(monkeypatch, {"files.example": ["93.184.216.34"]})
    transport = httpx.MockTransport(lambda request: httpx.Response(200, content=b"x" * 2048))
    dest = tmp_path / "big.media"
    with pytest.raises(UnsafeURLError):
        download_public_https("https://files.example/big.wav", str(dest), max_bytes=1024, transport=transport)
    assert not dest.exists()


# --- upload file names --------------------------------------------------------

SAFE_NAME = re.compile(r"^\d+_[0-9a-f]{8}_[A-Za-z0-9_-]{1,40}\.[a-z0-9]+$")


@pytest.mark.parametrize("filename,ext", [
    ("../../etc/passwd", ".audio"),
    ("..\\..\\Windows\\System32\\evil.mp3", ".mp3"),
    ("/abs/path/talk.WAV", ".wav"),
    ("C:\\Users\\x\\clip.m4a", ".m4a"),
    ("<script>alert(1)</script>.ogg", ".ogg"),
    ("shell.php", ".audio"),
    ("no_extension", ".audio"),
    ("....", ".audio"),
    ("", ".audio"),
    (None, ".audio"),
    ("a" * 500 + ".mp3", ".mp3"),
])
def test_safe_upload_name(filename, ext):
    name = safe_upload_name(filename)
    assert SAFE_NAME.match(name), name
    assert name.endswith(ext)
    assert "/" not in name and "\\" not in name and ".." not in name


def test_safe_upload_names_are_unique():
    assert safe_upload_name("a.mp3") != safe_upload_name("a.mp3")


def test_confined_path(tmp_path):
    base = tmp_path / "temp_audio"
    base.mkdir()
    inside = confined_path(str(base), safe_upload_name("../../x.mp3"))
    assert os.path.dirname(inside) == os.path.realpath(base)
    for bad in ["../escape.mp3", "..", ".", str(tmp_path / "elsewhere.mp3"), "sub/../../x.mp3"]:
        with pytest.raises(ValueError):
            confined_path(str(base), bad)
