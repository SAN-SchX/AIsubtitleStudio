import array
import wave

import pytest

from ai_subtitle_studio.domain.models import TranscriptSegment, WordTiming
from ai_subtitle_studio.speech.base import SpeechError, SpeechResult
from ai_subtitle_studio.speech.chunks import ChunkWindow, plan_chunks, write_chunk
from ai_subtitle_studio.speech.cues import make_cues
from ai_subtitle_studio.speech.stitch import append_chunk


def word(text, start, end):
    return WordTiming(text=text, start_ms=start, end_ms=end, confidence=0.9)


def segment(words, language="en"):
    return TranscriptSegment(
        id="x",
        text="".join(w.text for w in words).strip(),
        start_ms=words[0].start_ms,
        end_ms=words[-1].end_ms,
        words=words,
        language=language,
    )


def test_disjoint_cores_cover_movie_with_bounded_overlap():
    windows = plan_chunks(5400000)
    assert windows[0].core_start_ms == 0
    assert windows[-1].core_end_ms == 5400000
    assert all(w.end_ms - w.start_ms <= 30000 for w in windows)
    assert all(a.core_end_ms == b.core_start_ms for a, b in zip(windows, windows[1:], strict=False))
    assert windows[1].start_ms == 24000
    assert windows[0].end_ms == 26000


@pytest.mark.parametrize(
    "args",
    [
        {"duration_ms": 0},
        {"duration_ms": -1},
        {"duration_ms": 10, "core_ms": 0},
        {"duration_ms": 10, "context_ms": -1},
        {"duration_ms": 10, "core_ms": 30000, "context_ms": 1},
    ],
)
def test_invalid_chunk_configuration(args):
    with pytest.raises(ValueError):
        plan_chunks(**args)


def test_absolute_offsets_and_no_duplicate_boundary_words():
    output = []
    first = SpeechResult(
        language="en",
        segments=[segment([word(" First", 24500, 24700), word(" boundary", 24800, 25200)])],
    )
    append_chunk(output, first, ChunkWindow(0, 0, 26000, 0, 25000))
    second = SpeechResult(
        language="en", segments=[segment([word(" boundary", 800, 1200), word(" next", 1400, 1700)])]
    )
    append_chunk(output, second, ChunkWindow(1, 24000, 51000, 25000, 50000))
    words = [w for s in output for w in s.words]
    assert [w.text for w in words] == [" First", " boundary", " next"]
    assert [(w.start_ms, w.end_ms) for w in words] == [
        (24500, 24700),
        (24800, 25200),
        (25400, 25700),
    ]


def test_jitter_duplicate_removed_but_repeated_phrase_retained():
    output = []
    append_chunk(
        output,
        SpeechResult(language="en", segments=[segment([word(" Yes", 24700, 25200)])]),
        ChunkWindow(0, 0, 26000, 0, 25000),
    )
    append_chunk(
        output,
        SpeechResult(
            language="en", segments=[segment([word(" Yes", 900, 1400), word(" Yes", 1700, 2100)])]
        ),
        ChunkWindow(1, 24000, 51000, 25000, 50000),
    )
    assert [w.start_ms for s in output for w in s.words] == [24700, 25700]


def test_missing_word_timestamps_are_reported_not_invented():
    result = SpeechResult(
        language="pl",
        segments=[
            TranscriptSegment(id="a", text="Cześć", start_ms=1200, end_ms=2000, language="pl")
        ],
    )
    output = []
    warnings = append_chunk(output, result, ChunkWindow(1, 24000, 51000, 25000, 50000))
    assert "WORD_TIMESTAMPS_MISSING" in warnings
    assert (output[0].start_ms, output[0].end_ms) == (25200, 26000)


def test_out_of_bounds_fragment_rejected():
    result = SpeechResult(language="en", segments=[segment([word(" x", 0, 50000)])])
    with pytest.raises(SpeechError):
        append_chunk([], result, ChunkWindow(0, 0, 26000, 0, 25000))


def test_silence_gate_checks_short_frames(tmp_path):
    path = tmp_path / "source.wav"
    samples = array.array("h", [0] * 16000)
    samples[8000:8320] = array.array("h", [500] * 320)
    with wave.open(str(path), "wb") as writer:
        writer.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        writer.writeframes(samples.tobytes())
    assert write_chunk(path, tmp_path / "one.wav", ChunkWindow(0, 0, 1000, 0, 1000))
    assert not write_chunk(path, tmp_path / "two.wav", ChunkWindow(0, 0, 250, 0, 250))


def test_word_based_cues_preserve_unicode_times_and_unique_ids():
    segments = [
        segment([word(" Zażółć", 0, 1000), word(" gęślą.", 1200, 2000)], "pl"),
        segment([word("日本語", 3000, 4000), word("です。", 4000, 5000)], "ja"),
    ]
    cues, review, warnings = make_cues(segments)
    assert [c.text for c in cues] == ["Zażółć gęślą.", "日本語です。"]
    assert [(c.start_ms, c.end_ms) for c in cues] == [(0, 2000), (3000, 5000)]
    assert len({c.id for c in cues}) == 2
    assert not review
    assert not warnings


def test_long_segment_without_words_keeps_observed_endpoints_and_flags_review():
    s = TranscriptSegment(id="s", text="long " * 30, language="en", start_ms=100, end_ms=20100)
    cues, review, warnings = make_cues([s])
    assert (cues[0].start_ms, cues[0].end_ms) == (100, 20100)
    assert review == [cues[0].id]
    assert "CUE_REVIEW_REQUIRED" in warnings


def test_out_of_order_word_times_fail_without_publishing():
    result = SpeechResult(
        language="en",
        segments=[
            TranscriptSegment(
                id="x",
                text="a b",
                start_ms=0,
                end_ms=2000,
                language="en",
                words=[word(" a", 1000, 1500), word(" b", 0, 500)],
            )
        ],
    )
    with pytest.raises(SpeechError, match="nieuporządkowane czasy słów"):
        append_chunk([], result, ChunkWindow(0, 0, 3000, 0, 3000))
