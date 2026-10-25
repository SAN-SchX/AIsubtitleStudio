"""Opt-in real model checks. No corpus/model download and no synthetic speech claims."""

import json
import os
import platform
from pathlib import Path
from threading import Event

import pytest

from ai_subtitle_studio.speech.mlx_whisper import MlxSpeechProvider


@pytest.mark.parametrize("language", ["pl", "en", "ja"])
def test_real_mlx_on_local_speech(language):
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        pytest.skip("NOT VERIFIED: requires macOS Apple Silicon")
    corpus = os.environ.get("AISUBTITLE_ASR_CORPUS")
    model = os.environ.get("AISUBTITLE_MLX_MODEL_DIR")
    if not corpus or not model:
        pytest.skip("Provide AISUBTITLE_ASR_CORPUS and AISUBTITLE_MLX_MODEL_DIR; no downloads")
    manifest = json.loads(Path(corpus).read_text(encoding="utf-8"))
    sample = manifest[language]
    path = (Path(corpus).parent / sample["wav"]).resolve(strict=True)
    provider = MlxSpeechProvider(Path(model))
    try:
        result = provider.transcribe(path, language=language, cancel=Event())
        text = " ".join(s.text for s in result.segments).casefold()
        assert result.language == language
        assert result.segments
        assert sample["expected_phrase"].casefold() in text
        assert all(s.start_ms < s.end_ms for s in result.segments)
    finally:
        provider.close()
