import pytest
from pydantic import ValidationError

from ai_subtitle_studio.domain.models import (
    AudioTrack,
    JobConfig,
    MediaInfo,
    SubtitleCue,
    TranscriptSegment,
    WordTiming,
)


@pytest.mark.parametrize("start,end", [(-1, 2), (0, 0), (4, 2), (1.5, 3), (True, 3)])
def test_reject_invalid_times(start, end):
    with pytest.raises(ValidationError):
        SubtitleCue(id="a", text="日本語", start_ms=start, end_ms=end)


def test_unicode_and_original_timing():
    cue = SubtitleCue(
        id="a", text="Zażółć 日本語", start_ms=10, end_ms=20, original_start_ms=0, original_end_ms=9
    )
    assert cue.text == "Zażółć 日本語"
    with pytest.raises(ValidationError):
        cue.start_ms = 2


@pytest.mark.parametrize(
    "fields",
    [
        {"id": " "},
        {"text": "  "},
        {"original_start_ms": 2},
        {"original_start_ms": 4, "original_end_ms": 2},
    ],
)
def test_cue_validation(fields):
    args = dict(id="a", text="x", start_ms=0, end_ms=10)
    args.update(fields)
    with pytest.raises(ValidationError):
        SubtitleCue(**args)


def test_fps_and_stream_validation():
    with pytest.raises(ValidationError):
        MediaInfo(duration_ms=0, fps_num=25)
    with pytest.raises(ValidationError):
        MediaInfo(duration_ms=10, audio_tracks=[AudioTrack(stream_index=1)] * 2)


def test_transcript_contract():
    segment = TranscriptSegment(
        id="s1",
        text="hi",
        language="en",
        start_ms=0,
        end_ms=100,
        words=[WordTiming(text="hi", start_ms=0, end_ms=100)],
    )
    assert segment.words[0].end_ms == 100
    with pytest.raises(ValidationError):
        WordTiming(text="hi", start_ms=0, end_ms=100, confidence=1.1)


def test_job_config_is_typed(tmp_path):
    cfg = JobConfig(video_path=tmp_path / "film.mkv", mode="inspect")
    assert cfg.audio_stream_index is None
    assert cfg.quality_preset == "memory_safe"
    with pytest.raises(ValidationError):
        JobConfig(video_path="film.mkv", mode="pretend")
