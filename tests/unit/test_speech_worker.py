from unittest.mock import Mock

import pytest

from ai_subtitle_studio.speech.base import SpeechError
from ai_subtitle_studio.speech.mlx_worker import decode_chunk, parse_mlx_result


def raw_result(language="pl"):
    return {
        "language": language,
        "segments": [
            {
                "start": 0.1,
                "end": 1.5,
                "text": " Zażółć 日本語",
                "avg_logprob": -0.1,
                "no_speech_prob": 0.01,
                "words": [
                    {"start": 0.1, "end": 0.7, "word": " Zażółć", "probability": 0.9},
                    {"start": 0.8, "end": 1.5, "word": " 日本語", "probability": 0.95},
                ],
            }
        ],
    }


@pytest.mark.parametrize("language", ["en", "pl", "ja"])
def test_decode_passes_actual_local_model_and_override(model_dir, tmp_path, language):
    transcribe = Mock(return_value=raw_result(language))
    result = decode_chunk(transcribe, tmp_path / "chunk.wav", model_dir, language)
    kwargs = transcribe.call_args.kwargs
    assert kwargs["language"] == language
    assert kwargs["path_or_hf_repo"] == str(model_dir)
    assert kwargs["task"] == "transcribe"
    assert kwargs["word_timestamps"] is True
    assert kwargs["verbose"] is None
    assert result.language == language
    assert result.segments[0].start_ms == 100
    assert result.segments[0].words[-1].end_ms == 1500


def test_auto_language_argument_is_none(model_dir, tmp_path):
    transcribe = Mock(return_value=raw_result("ja"))
    decode_chunk(transcribe, tmp_path / "chunk.wav", model_dir, None)
    assert transcribe.call_args.kwargs["language"] is None


@pytest.mark.parametrize(
    "changes",
    [
        {"start": -1},
        {"end": 0},
        {"avg_logprob": float("nan")},
        {"words": [{"word": "x", "start": 0, "end": 10}]},
    ],
)
def test_invalid_backend_times_do_not_get_exported(changes):
    raw = raw_result()
    raw["segments"][0].update(changes)
    with pytest.raises(SpeechError):
        parse_mlx_result(raw)


def test_no_speech_hypothesis_rejected():
    raw = raw_result()
    raw["segments"][0].update(no_speech_prob=0.9, avg_logprob=-2)
    result = parse_mlx_result(raw)
    assert not result.segments
    assert "NO_SPEECH_SEGMENTS_REJECTED" in result.warnings


def test_invalid_model_never_reaches_transcribe(tmp_path):
    transcribe = Mock()
    with pytest.raises(SpeechError):
        decode_chunk(transcribe, tmp_path / "chunk.wav", tmp_path / "missing", "pl")
    transcribe.assert_not_called()


def test_zero_duration_word_keeps_complete_segment_text():
    raw = raw_result()
    raw["segments"][0]["words"][0]["end"] = 0.1
    result = parse_mlx_result(raw)
    assert result.segments[0].text == "Zażółć 日本語"
    assert not result.segments[0].words
    assert "WORD_TIMESTAMPS_MISSING" in result.warnings
