import array
import math
import wave
from threading import Event

import pytest

from ai_subtitle_studio.domain.errors import (
    InvalidMediaError,
    OperationCancelled,
    OutputConflictError,
)
from ai_subtitle_studio.media.extract import extract_audio
from ai_subtitle_studio.media.probe import probe_media

pytestmark = pytest.mark.integration


def read_wave(path):
    with wave.open(str(path)) as reader:
        assert reader.getnchannels() == 1
        assert reader.getframerate() == 16000
        assert reader.getsampwidth() == 2
        samples = array.array("h", reader.readframes(reader.getnframes()))
    return samples


def test_probe_real_multi_audio_and_unicode(media_files):
    info = probe_media(media_files["multi"])
    assert abs(info.duration_ms - 1520) <= 60
    assert (info.fps_num, info.fps_den) == (25, 1)
    assert [t.stream_index for t in info.audio_tracks] == [1, 2]
    assert [t.language for t in info.audio_tracks] == ["jpn", "eng"]
    assert info.audio_tracks[0].title == "日本語"


@pytest.mark.parametrize("index,frequency", [(1, 440), (2, 880)])
def test_extracts_selected_stream_not_first(media_files, tmp_path, index, frequency):
    target = tmp_path / f"track-{index}.wav"
    original = media_files["multi"].read_bytes()
    extract_audio(media_files["multi"], target, index)
    samples = read_wave(target)[1600:16000]
    crossings = sum(a <= 0 < b for a, b in zip(samples, samples[1:], strict=False))
    measured = crossings / (len(samples) / 16000)
    assert abs(measured - frequency) < 3
    assert media_files["multi"].read_bytes() == original
    with pytest.raises(OutputConflictError):
        extract_audio(media_files["multi"], target, index)
    assert not list(tmp_path.glob(".aisub-*"))


def test_delayed_audio_preserves_video_timeline_and_nonzero_pts(media_files, tmp_path):
    info = probe_media(media_files["delayed"])
    assert info.start_time_ms == 3000
    assert info.audio_tracks[0].start_time_ms == 3250
    target = tmp_path / "delayed.wav"
    extract_audio(media_files["delayed"], target, 1)
    samples = read_wave(target)
    assert max(map(abs, samples[:3000])) == 0  # first 187.5 ms are silence
    assert math.sqrt(sum(s * s for s in samples[4500:8000]) / 3500) > 1000
    onset = next(i for i, value in enumerate(samples) if abs(value) > 100)
    assert abs(onset / 16 - 250) < 2


def test_silent_and_corrupt_inputs(media_files, tmp_path):
    assert probe_media(media_files["silent"]).audio_tracks == []
    with pytest.raises(InvalidMediaError, match="nie zawiera"):
        extract_audio(media_files["silent"], tmp_path / "none.wav", 0)
    with pytest.raises(InvalidMediaError):
        probe_media(media_files["corrupt"])
    with pytest.raises(InvalidMediaError, match="nie jest ścieżką"):
        extract_audio(media_files["multi"], tmp_path / "wrong.wav", 0)
    assert not list(tmp_path.glob("*.wav"))


def test_repeated_cancel_leaves_no_output(media_files, tmp_path):
    cancel = Event()
    cancel.set()
    for _ in range(3):
        with pytest.raises(OperationCancelled):
            extract_audio(media_files["multi"], tmp_path / "cancel.wav", 1, cancel=cancel)
    assert not list(tmp_path.iterdir())


def test_cancel_running_ffmpeg_removes_partial_wav(media_files, tmp_path, monkeypatch):
    import threading

    from ai_subtitle_studio.media import extract, process

    cancel = Event()
    children = []
    original_popen = process.subprocess.Popen
    original_run = extract.run_tool

    def record_child(*args, **kwargs):
        child = original_popen(*args, **kwargs)
        children.append(child)
        return child

    def paced_ffmpeg(argv, **kwargs):
        # Throttle a real short FFmpeg extraction so cancellation reliably lands
        # mid-process. All actual extraction arguments/cleanup remain in use.
        argv = list(argv)
        argv.insert(argv.index("-i"), "-re")
        timer = threading.Timer(0.2, cancel.set)
        timer.start()
        try:
            return original_run(argv, **kwargs)
        finally:
            timer.join()

    monkeypatch.setattr(process.subprocess, "Popen", record_child)
    monkeypatch.setattr(extract, "run_tool", paced_ffmpeg)
    with pytest.raises(OperationCancelled):
        extract_audio(media_files["multi"], tmp_path / "partial.wav", 1, cancel=cancel)
    assert len(children) == 2  # FFprobe then FFmpeg
    assert all(child.poll() is not None for child in children)
    assert not list(tmp_path.iterdir())
