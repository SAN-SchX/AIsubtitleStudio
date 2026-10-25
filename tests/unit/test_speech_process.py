import sys
from pathlib import Path
from threading import Event, Timer

import pytest

from ai_subtitle_studio.domain.errors import OperationCancelled
from ai_subtitle_studio.speech import mlx_whisper
from ai_subtitle_studio.speech.base import SpeechError

# This test executable emulates the transport protocol only; no fake backend in production.
TRANSPORT = """
import json, os, sys, time
from pathlib import Path
root, mode = Path(sys.argv[1]), sys.argv[2]
assert os.environ["HF_HUB_OFFLINE"] == "1"
assert os.environ["HF_HUB_DISABLE_TELEMETRY"] == "1"
for line in sys.stdin:
    r = json.loads(line)
    if mode == "hang": time.sleep(60)
    if mode == "exit": sys.exit(2)
    value = {"language": r["language"] or "pl", "segments": [], "warnings": []}
    text = "malformed" if mode == "bad" else json.dumps(value)
    if mode == "memory": text = json.dumps({"error": "out_of_memory"})
    target = root / ("response-" + str(r["sequence"]) + ".json")
    temp = target.with_suffix(".tmp")
    temp.write_text(text)
    os.replace(temp, target)
"""


@pytest.fixture
def provider_factory(monkeypatch, model_dir, tmp_path):
    monkeypatch.setattr(mlx_whisper, "backend_problem", lambda: None)
    program = tmp_path / "transport_test.py"
    program.write_text(TRANSPORT)
    providers = []

    def create(mode="ok", timeout=3):
        provider = mlx_whisper.MlxSpeechProvider(model_dir, timeout_s=timeout)
        monkeypatch.setattr(
            provider, "_command", lambda: [sys.executable, str(program), provider._work.name, mode]
        )
        providers.append(provider)
        return provider

    yield create
    for provider in providers:
        provider.close()


def test_process_reused_then_reaped(provider_factory, tmp_path):
    provider = provider_factory()
    wav = tmp_path / "chunk.wav"
    wav.touch()
    assert provider.transcribe(wav, language=None, cancel=Event()).language == "pl"
    child = provider._process
    assert provider.transcribe(wav, language="ja", cancel=Event()).language == "ja"
    assert provider._process is child
    assert child.poll() is None
    provider.close()
    provider.close()
    assert child.poll() is not None
    assert not Path(provider._work.name).exists()


@pytest.mark.parametrize(
    "mode,message",
    [("bad", "odpowiedź"), ("memory", "pamięci"), ("exit", "zakończył"), ("hang", "limit czasu")],
)
def test_process_failures_reap_and_cleanup(provider_factory, tmp_path, mode, message):
    provider = provider_factory(mode, timeout=0.2)
    wav = tmp_path / "chunk.wav"
    wav.touch()
    with pytest.raises(SpeechError, match=message):
        provider.transcribe(wav, language="pl", cancel=Event())
    assert provider._process.poll() is not None
    assert not Path(provider._work.name).exists()


def test_cancel_during_model_work_reaps_process(provider_factory, tmp_path):
    provider = provider_factory("hang")
    wav = tmp_path / "chunk.wav"
    wav.touch()
    cancel = Event()
    timer = Timer(0.1, cancel.set)
    timer.start()
    try:
        with pytest.raises(OperationCancelled):
            provider.transcribe(wav, language="en", cancel=cancel)
    finally:
        timer.join()
    assert provider._process.poll() is not None
    assert not Path(provider._work.name).exists()
