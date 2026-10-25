"""Private subprocess entry point. Model remains loaded between bounded chunks."""

import argparse
import json
import math
import os
import sys
from pathlib import Path

from pydantic import ValidationError

from ai_subtitle_studio.domain.models import TranscriptSegment, WordTiming
from ai_subtitle_studio.speech.base import SpeechError, SpeechResult
from ai_subtitle_studio.speech.models import backend_problem, validate_model


def parse_mlx_result(raw: dict) -> SpeechResult:
    try:
        language = raw["language"]
        segments = []
        warnings = set()
        for index, segment in enumerate(raw["segments"]):
            text = segment["text"].strip()
            if not text:
                continue
            if segment.get("no_speech_prob", 0) > 0.6 and segment.get("avg_logprob", 0) < -1:
                warnings.add("NO_SPEECH_SEGMENTS_REJECTED")
                continue
            start, end = round(segment["start"] * 1000), round(segment["end"] * 1000)
            words = []
            missing_word_times = False
            for word in segment.get("words", []):
                a, b = round(word["start"] * 1000), round(word["end"] * 1000)
                if a == b:
                    missing_word_times = True
                    continue
                if a < start - 20 or b > end + 20:
                    raise ValueError("Word lies outside segment")
                words.append(
                    WordTiming(
                        text=word["word"],
                        start_ms=max(start, a),
                        end_ms=min(end, b),
                        confidence=word.get("probability"),
                    )
                )
            if missing_word_times:
                # Keep the complete observed segment text rather than silently
                # dropping a word that the model failed to time.
                words = []
                warnings.add("WORD_TIMESTAMPS_MISSING")
            logprob = segment.get("avg_logprob")
            if logprob is not None and not math.isfinite(logprob):
                raise ValueError("Non-finite log probability")
            confidence = min(1.0, math.exp(logprob)) if logprob is not None else None
            segments.append(
                TranscriptSegment(
                    id=f"local-{index}",
                    text=text,
                    start_ms=start,
                    end_ms=end,
                    language=language,
                    words=words,
                    confidence=confidence,
                )
            )
        return SpeechResult(language=language, segments=segments, warnings=sorted(warnings))
    except (ValueError, TypeError, KeyError, OverflowError, ValidationError) as exc:
        raise SpeechError("Nieprawidłowe czasy lub dane wyniku MLX.") from exc


def decode_chunk(transcribe, wav: Path, model: Path, language: str | None) -> SpeechResult:
    # Never pass a repository ID: existing local path plus HF_HUB_OFFLINE=1.
    validate_model(model)
    raw = transcribe(
        str(wav),
        path_or_hf_repo=str(model),
        language=language,
        task="transcribe",
        verbose=None,
        word_timestamps=True,
        condition_on_previous_text=False,
        temperature=0.0,
        no_speech_threshold=0.6,
        hallucination_silence_threshold=2.0,
    )
    return parse_mlx_result(raw)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--work-dir", type=Path, required=True)
    args = parser.parse_args()
    if backend_problem():
        return 1
    model = validate_model(args.model_dir)
    os.environ.update(
        HF_HUB_OFFLINE="1", HF_HUB_DISABLE_TELEMETRY="1", TRANSFORMERS_OFFLINE="1", DO_NOT_TRACK="1"
    )
    import mlx_whisper

    for line in sys.stdin:
        request = json.loads(line)
        target = args.work_dir / f"response-{int(request['sequence'])}.json"
        try:
            result = decode_chunk(
                mlx_whisper.transcribe, Path(request["wav"]), model, request["language"]
            ).model_dump()
        except MemoryError:
            result = {"error": "out_of_memory"}
        except Exception:
            result = {"error": "backend_failure"}
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False), encoding="utf-8")
        os.replace(temporary, target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
