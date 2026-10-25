import json
from unittest.mock import Mock

import pytest

from ai_subtitle_studio import doctor
from ai_subtitle_studio.cli import main
from ai_subtitle_studio.config import Settings


def mock_http(monkeypatch, *, status=200, payload=b'{"models": []}'):
    connection = Mock()
    response = connection.getresponse.return_value
    response.status = status
    response.read.return_value = payload
    factory = Mock(return_value=connection)
    monkeypatch.setattr(doctor, "HTTPConnection", factory)
    return factory, connection


def test_fixed_loopback_models_and_no_redirects(monkeypatch):
    factory, connection = mock_http(monkeypatch, payload=b'{"models": [{"name": "qwen3:4b"}]}')
    assert doctor.ollama_models() == {"qwen3:4b"}
    factory.assert_called_once_with("127.0.0.1", 11434, timeout=1.0)
    connection.request.assert_called_once_with("GET", "/api/tags")
    connection.close.assert_called_once()


@pytest.mark.parametrize(
    "status,payload", [(302, b""), (200, b"not json"), (200, b"x" * (1024 * 1024 + 1))]
)
def test_malformed_local_service(monkeypatch, status, payload):
    _, connection = mock_http(monkeypatch, status=status, payload=payload)
    with pytest.raises(ValueError):
        doctor.ollama_models()
    connection.close.assert_called_once()


def test_ollama_missing_is_optional_but_ffmpeg_required(monkeypatch):
    def unavailable():
        raise ConnectionRefusedError()

    monkeypatch.setattr(doctor, "ollama_models", unavailable)
    checks = doctor.diagnose(Settings(ffmpeg="/missing/ffmpeg", ffprobe="/missing/ffprobe"))
    assert any(c.name == "Ollama" and not c.ok and not c.required for c in checks)
    assert any(c.name == "FFmpeg" and not c.ok and c.required for c in checks)


def test_cli_diagnostics_exit_status_and_json(monkeypatch, capsys):
    monkeypatch.setattr(
        doctor, "diagnose", lambda **kw: [doctor.Check("required", False, True, "x")]
    )
    assert main(["doctor", "--json", "--no-ollama"]) == 1
    assert json.loads(capsys.readouterr().out)[0]["ok"] is False
    monkeypatch.setattr(
        doctor, "diagnose", lambda **kw: [doctor.Check("optional", False, False, "x")]
    )
    assert main(["doctor"]) == 0
    assert "UWAGA" in capsys.readouterr().out


@pytest.mark.parametrize("exception", [TimeoutError, ConnectionRefusedError])
def test_ollama_timeout_or_offline_is_reported(monkeypatch, exception):
    def unavailable():
        raise exception()

    monkeypatch.setattr(doctor, "ollama_models", unavailable)
    monkeypatch.setattr(doctor, "run_tool", lambda *a, **kw: b"version 1")
    checks = doctor.diagnose()
    assert any(c.name == "Ollama" and not c.ok and not c.required for c in checks)
