import logging
import wave
from threading import Event

import pytest

from ai_subtitle_studio.domain.errors import OperationCancelled, OutputConflictError
from ai_subtitle_studio.domain.models import JobConfig, TranscriptSegment, WordTiming
from ai_subtitle_studio.jobs.transcribe import transcribe_video
from ai_subtitle_studio.speech.base import SpeechError, SpeechResult
from ai_subtitle_studio.subtitles.io import load_subtitles, save_cues


class GroundTruthProvider:
    """Test-only provider: validates real PCM and returns explicit fixture timings."""

    model_id = "test-ground-truth"

    def __init__(self, language="pl", cancel=None, fail=False):
        self.calls = []
        self.closed = False
        self.language = language
        self.cancel = cancel
        self.fail = fail

    def transcribe(self, wav, *, language, cancel):
        with wave.open(str(wav)) as reader:
            assert (reader.getframerate(), reader.getnchannels(), reader.getsampwidth()) == (
                16000,
                1,
                2,
            )
            assert reader.getnframes() <= 30000 * 16
        self.calls.append(language)
        if self.fail:
            raise SpeechError("test failure")
        if self.cancel:
            self.cancel.set()
        text = {"pl": "Zażółć", "en": "Hello", "ja": "日本語"}[self.language]
        return SpeechResult(
            language=self.language,
            segments=[
                TranscriptSegment(
                    id="test",
                    text=text,
                    language=self.language,
                    start_ms=100,
                    end_ms=250,
                    words=[WordTiming(text=text, start_ms=100, end_ms=250, confidence=0.95)],
                )
            ],
        )

    def close(self):
        self.closed = True


@pytest.mark.parametrize("language", ["pl", "en", "ja"])
def test_real_ffmpeg_pipeline_and_ground_truth_srt(media_files, tmp_path, language, caplog):
    provider = GroundTruthProvider(language)
    config = JobConfig(
        video_path=media_files["multi"],
        audio_stream_index=2,
        source_language=language,
        mode="transcribe",
    )
    output = tmp_path / f"{language}.srt"
    progress = []
    caplog.set_level(logging.INFO, logger="ai_subtitle_studio.jobs.transcribe")
    result = transcribe_video(
        config, output, provider, progress=progress.append, core_ms=500, context_ms=100
    )
    cues = load_subtitles(output).cues
    # Actual WAV is 1.5s: windows [0,600], [400,1100], [900,1500].
    assert [(c.start_ms, c.end_ms) for c in cues] == [(100, 250), (500, 650), (1000, 1150)]
    assert provider.calls == [language] * 3
    assert provider.closed
    assert result.metrics["chunks_completed"] == 3
    assert result.metrics["elapsed_s"] > 0
    assert progress[-1].stage == "Zapis SRT"
    assert [(p.completed, p.total) for p in progress if p.stage == "Transkrypcja"] == [
        (0, 3),
        (1, 3),
        (2, 3),
        (3, 3),
    ]
    assert "test-ground-truth" in caplog.text
    assert cues[0].text not in caplog.text


def test_auto_language_is_detected_then_locked(media_files, tmp_path):
    provider = GroundTruthProvider("ja")
    cfg = JobConfig(video_path=media_files["multi"], audio_stream_index=1, mode="transcribe")
    transcribe_video(cfg, tmp_path / "auto.srt", provider, core_ms=500, context_ms=100)
    assert provider.calls == [None, "ja", "ja"]


@pytest.mark.parametrize("cancelled", [False, True])
def test_provider_failure_or_cancel_publishes_nothing(media_files, tmp_path, cancelled):
    cancel = Event()
    provider = GroundTruthProvider(cancel=cancel if cancelled else None, fail=not cancelled)
    cfg = JobConfig(video_path=media_files["multi"], audio_stream_index=1, mode="transcribe")
    with pytest.raises(OperationCancelled if cancelled else SpeechError):
        transcribe_video(cfg, tmp_path / "out.srt", provider, cancel=cancel)
    assert provider.closed
    assert not list(tmp_path.iterdir())


def test_existing_output_fails_before_extraction_and_closes_provider(media_files, tmp_path):
    provider = GroundTruthProvider()
    cfg = JobConfig(video_path=media_files["multi"], audio_stream_index=1, mode="transcribe")
    target = tmp_path / "existing.srt"
    target.write_text("original")
    with pytest.raises(OutputConflictError):
        transcribe_video(cfg, target, provider)
    assert target.read_text() == "original"
    assert not provider.calls
    assert provider.closed


def test_no_speech_does_not_fabricate_output(media_files, tmp_path):
    class NoSpeech(GroundTruthProvider):
        def transcribe(self, wav, *, language, cancel):
            return SpeechResult(language="pl", segments=[])

    provider = NoSpeech()
    cfg = JobConfig(video_path=media_files["multi"], audio_stream_index=1, mode="transcribe")
    with pytest.raises(SpeechError, match="Nie wykryto"):
        transcribe_video(cfg, tmp_path / "none.srt", provider)
    assert provider.closed
    assert not list(tmp_path.iterdir())


def test_cancellation_immediately_before_publish_preserves_source(fixtures_dir, tmp_path):
    cues = load_subtitles(fixtures_dir / "pl_reference.srt").cues
    event = Event()
    event.set()
    with pytest.raises(OperationCancelled):
        save_cues(list(cues), tmp_path / "cancel.srt", cancel=event)
    assert not list(tmp_path.iterdir())


def test_no_disk_space_never_starts_extraction(media_files, tmp_path, monkeypatch):
    from collections import namedtuple

    from ai_subtitle_studio.jobs import transcribe

    usage = namedtuple("Usage", "total used free")
    monkeypatch.setattr(transcribe.shutil, "disk_usage", lambda _: usage(100, 100, 0))
    provider = GroundTruthProvider()
    cfg = JobConfig(video_path=media_files["multi"], audio_stream_index=1, mode="transcribe")
    with pytest.raises(SpeechError, match="wolnego miejsca"):
        transcribe_video(cfg, tmp_path / "out.srt", provider)
    assert provider.closed
    assert not provider.calls
    assert not list(tmp_path.iterdir())
