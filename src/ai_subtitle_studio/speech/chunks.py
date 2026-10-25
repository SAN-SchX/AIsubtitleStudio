"""Bounded WAV windows with disjoint ownership cores and overlapping context."""

import array
import math
import sys
import wave
from dataclasses import dataclass
from pathlib import Path

from ai_subtitle_studio.speech.base import SpeechError


@dataclass(frozen=True)
class ChunkWindow:
    index: int
    start_ms: int
    end_ms: int
    core_start_ms: int
    core_end_ms: int


def plan_chunks(
    duration_ms: int, *, core_ms: int = 25000, context_ms: int = 1000
) -> list[ChunkWindow]:
    if duration_ms <= 0 or core_ms <= 0 or context_ms < 0 or core_ms + 2 * context_ms > 30000:
        raise ValueError("Chunk duration must be in (0, 30s] including context")
    return [
        ChunkWindow(
            i,
            max(0, start - context_ms),
            min(duration_ms, start + core_ms + context_ms),
            start,
            min(duration_ms, start + core_ms),
        )
        for i, start in enumerate(range(0, duration_ms, core_ms))
    ]


def wav_duration_ms(path: Path) -> int:
    with wave.open(str(path), "rb") as reader:
        if (reader.getnchannels(), reader.getframerate(), reader.getsampwidth()) != (1, 16000, 2):
            raise SpeechError("Wymagany WAV PCM 16 bit, 16 kHz mono.")
        return math.ceil(reader.getnframes() / 16)


def write_chunk(source: Path, target: Path, window: ChunkWindow) -> bool:
    """Decode at most 30s into memory; return False for near-digital silence.

    This is an amplitude gate, NOT a speech/music classifier or Silero VAD.
    """
    with wave.open(str(source), "rb") as reader:
        if (reader.getnchannels(), reader.getframerate(), reader.getsampwidth()) != (1, 16000, 2):
            raise SpeechError("Wymagany WAV PCM 16 bit, 16 kHz mono.")
        reader.setpos(window.start_ms * 16)
        raw = reader.readframes((window.end_ms - window.start_ms) * 16)
    with wave.open(str(target), "wb") as writer:
        writer.setparams((1, 2, 16000, 0, "NONE", "not compressed"))
        writer.writeframes(raw)
    samples = array.array("h", raw)
    if sys.byteorder != "little":
        samples.byteswap()
    # Do not miss short utterances diluted by 25s of silence: inspect 20ms frames.
    return any(
        sum(s * s for s in samples[i : i + 320]) > 30 * 30 * len(samples[i : i + 320])
        for i in range(0, len(samples), 320)
    )
