import json
import sys
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from ai_subtitle_studio.speech import models
from ai_subtitle_studio.speech.base import SpeechError


def test_local_model_validation_no_network(model_dir):
    assert models.validate_model(model_dir) == model_dir.resolve()
    (model_dir / "weights.safetensors").unlink()
    with pytest.raises(SpeechError, match="Brak lokalnego"):
        models.validate_model(model_dir)


@pytest.mark.parametrize("content", ["not json", "[]", "{}", '{"n_vocab":1}'])
def test_invalid_config(model_dir, content):
    (model_dir / "config.json").write_text(content)
    with pytest.raises(SpeechError):
        models.validate_model(model_dir)


def test_backend_platform_and_version(monkeypatch):
    monkeypatch.setattr(models.platform, "system", lambda: "Linux")
    assert "macOS" in models.backend_problem()
    monkeypatch.setattr(models.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(models.platform, "machine", lambda: "arm64")
    monkeypatch.setattr(models.importlib.metadata, "version", lambda _: "wrong")
    assert "0.4.3" in models.backend_problem()
    monkeypatch.setattr(models.importlib.metadata, "version", lambda _: "0.4.3")
    assert models.backend_problem() is None


def test_download_requires_consent_before_any_network_or_import(tmp_path):
    with pytest.raises(SpeechError, match="jawnej zgody"):
        models.download_model("speed", tmp_path / "not-created")
    assert not list(tmp_path.iterdir())


def test_explicit_download_uses_only_model_assets(tmp_path, monkeypatch):
    def snapshot(**kwargs):
        destination = tmp_path / "download"
        destination.mkdir()
        (destination / "config.json").write_text(json.dumps({"n_vocab": 10, "n_mels": 80}))
        (destination / "weights.npz").write_bytes(b"test-fixture")

    download = Mock(side_effect=snapshot)
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=download))
    target = models.download_model("speed", tmp_path / "download", consent=True)
    assert target == tmp_path / "download"
    call = download.call_args.kwargs
    assert call["repo_id"] == models.PRESETS["speed"]
    assert call["allow_patterns"] == ["config.json", "weights.safetensors", "weights.npz"]
    assert not call.get("token")
    models.download_model("speed", target, consent=True)
    assert download.call_count == 1


def test_download_never_replaces_existing_invalid_directory(tmp_path, monkeypatch):
    download = Mock()
    monkeypatch.setitem(sys.modules, "huggingface_hub", SimpleNamespace(snapshot_download=download))
    target = tmp_path / "mine"
    target.mkdir()
    (target / "valuable").write_text("original")
    with pytest.raises(SpeechError, match="Folder już istnieje"):
        models.download_model("speed", target, consent=True)
    download.assert_not_called()
    assert (target / "valuable").read_text() == "original"


def test_download_failure_is_actionable(tmp_path, monkeypatch):
    monkeypatch.setitem(
        sys.modules,
        "huggingface_hub",
        SimpleNamespace(snapshot_download=Mock(side_effect=OSError("no route"))),
    )
    with pytest.raises(SpeechError, match="TLS"):
        models.download_model("accurate", tmp_path / "new", consent=True)
