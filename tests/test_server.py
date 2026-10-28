"""Request validation in server.py, with the agent subprocess stubbed out."""
import base64
import http.client
import importlib
import json
import os
import threading
from http.server import HTTPServer

import pytest

import server


class FakePopen:
    calls = []
    started = threading.Event()

    def __init__(self, cmd, **kwargs):
        FakePopen.calls.append(cmd)
        self.stdout = iter(())
        FakePopen.started.set()

    def wait(self):
        return 0


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "web" / "data").mkdir(parents=True)
    FakePopen.calls = []
    FakePopen.started.clear()
    monkeypatch.setattr(server.subprocess, "Popen", FakePopen)
    httpd = HTTPServer(("127.0.0.1", 0), server.OmniSightHandler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    yield httpd.server_address[1]
    httpd.shutdown()
    httpd.server_close()


def post(port, payload, headers=None):
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    body = json.dumps(payload).encode()
    conn.request("POST", "/api/run", body=body, headers={"Content-Type": "application/json", **(headers or {})})
    resp = conn.getresponse()
    resp.read()
    conn.close()
    return resp.status


@pytest.mark.parametrize("audio_url", [
    "http://169.254.169.254/latest/meta-data/",
    "https://127.0.0.1:8000/data/status.txt",
    "file:///etc/passwd",
])
def test_unsafe_audio_url_is_rejected_before_scan(app, audio_url):
    assert post(app, {"target": "Acme", "audio_url": audio_url}) == 400
    assert FakePopen.calls == []


def test_upload_name_cannot_escape_audio_dir(app, tmp_path):
    audio = base64.b64encode(b"fake-audio").decode()
    status = post(app, {"target": "Acme", "audio": "data:audio/mpeg;base64," + audio, "filename": "../../evil.py"})
    assert status == 200
    assert FakePopen.started.wait(5)
    cmd = FakePopen.calls[0]
    saved = cmd[cmd.index("--audio") + 1]
    audio_dir = os.path.realpath(tmp_path / "temp_audio")
    assert os.path.dirname(os.path.realpath(saved)) == audio_dir
    assert saved.endswith(".audio") and "evil" in os.path.basename(saved)
    with open(saved, "rb") as f:
        assert f.read() == b"fake-audio"
    assert not (tmp_path / "evil.py").exists()
    assert not (tmp_path.parent / "evil.py").exists()


def test_target_is_passed_after_double_dash(app):
    assert post(app, {"target": "--audio=/etc/passwd"}) == 200
    assert FakePopen.started.wait(5)
    assert FakePopen.calls[0][-2:] == ["--", "--audio=/etc/passwd"]
    assert "--audio" not in FakePopen.calls[0][:-1]


@pytest.mark.parametrize("payload", [{}, {"target": ""}, {"target": 42}, {"target": "x" * 500}])
def test_invalid_target_is_rejected(app, payload):
    assert post(app, payload) == 400
    assert FakePopen.calls == []


def test_oversized_body_is_rejected_without_reading_it(app):
    conn = http.client.HTTPConnection("127.0.0.1", app, timeout=10)
    conn.putrequest("POST", "/api/run")
    conn.putheader("Content-Type", "application/json")
    conn.putheader("Content-Length", str(server.MAX_BODY_BYTES + 1))
    conn.endheaders()
    assert conn.getresponse().status == 413
    conn.close()


def test_binds_to_localhost_by_default(monkeypatch):
    monkeypatch.delenv("HOST", raising=False)
    assert importlib.reload(server).HOST == "127.0.0.1"
    monkeypatch.setenv("HOST", "0.0.0.0")
    assert importlib.reload(server).HOST == "0.0.0.0"
    monkeypatch.delenv("HOST")
    importlib.reload(server)
