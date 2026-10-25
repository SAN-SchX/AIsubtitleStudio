"""Audio-grounded ownership and conservative overlap deduplication (no retiming)."""

import re
import unicodedata

from ai_subtitle_studio.domain.models import TranscriptSegment, WordTiming
from ai_subtitle_studio.speech.base import SpeechError, SpeechResult
from ai_subtitle_studio.speech.chunks import ChunkWindow


def join_words(words: list[WordTiming], language: str) -> str:
    if language in {"ja", "zh"} or any(w.text[:1].isspace() for w in words):
        return "".join(w.text for w in words).strip()
    text = " ".join(w.text.strip() for w in words)
    return re.sub(r"\s+([.,!?;:])", r"\1", text)


def _key(text: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKC", text).casefold() if c.isalnum())


def _same_occurrence(a: WordTiming | TranscriptSegment, b: WordTiming | TranscriptSegment) -> bool:
    overlap = min(a.end_ms, b.end_ms) - max(a.start_ms, b.start_ms)
    duration = min(a.end_ms - a.start_ms, b.end_ms - b.start_ms)
    return (
        bool(_key(a.text))
        and _key(a.text) == _key(b.text)
        and abs(a.start_ms - b.start_ms) <= 250
        and overlap >= duration * 0.3
    )


def append_chunk(
    output: list[TranscriptSegment],
    result: SpeechResult,
    window: ChunkWindow,
) -> set[str]:
    warnings = set(result.warnings)
    recent_words = [
        w for s in output[-10:] for w in s.words if w.end_ms >= window.core_start_ms - 1000
    ]
    previous_start = -1
    for segment in result.segments:
        if (
            segment.start_ms < previous_start
            or segment.end_ms > window.end_ms - window.start_ms + 20
        ):
            raise SpeechError("Backend zwrócił nieuporządkowane lub zbyt długie czasy fragmentu.")
        previous_start = segment.start_ms
        offset = window.start_ms
        if not segment.text.strip():
            raise SpeechError("Backend zwrócił pustą treść segmentu.")
        if segment.words:
            if any(
                a.start_ms > b.start_ms
                for a, b in zip(segment.words, segment.words[1:], strict=False)
            ):
                raise SpeechError("Backend zwrócił nieuporządkowane czasy słów.")
            retained = []
            for word in segment.words:
                if word.start_ms < segment.start_ms or word.end_ms > segment.end_ms:
                    raise SpeechError("Czas słowa wychodzi poza segment transkrypcji.")
                absolute = WordTiming(
                    text=word.text,
                    start_ms=word.start_ms + offset,
                    end_ms=word.end_ms + offset,
                    confidence=word.confidence,
                )
                midpoint = (absolute.start_ms + absolute.end_ms) / 2
                if window.core_start_ms <= midpoint < window.core_end_ms:
                    if not any(_same_occurrence(absolute, other) for other in recent_words):
                        retained.append(absolute)
            if not retained:
                continue
            text = (
                segment.text
                if len(retained) == len(segment.words)
                else join_words(retained, segment.language)
            )
            candidate = TranscriptSegment(
                id=f"segment-{len(output) + 1:06d}",
                text=text,
                start_ms=retained[0].start_ms,
                end_ms=retained[-1].end_ms,
                words=retained,
                language=segment.language,
                confidence=segment.confidence,
            )
        else:
            warnings.add("WORD_TIMESTAMPS_MISSING")
            midpoint = (segment.start_ms + segment.end_ms) / 2 + offset
            if not window.core_start_ms <= midpoint < window.core_end_ms:
                continue
            candidate = TranscriptSegment(
                id=f"segment-{len(output) + 1:06d}",
                text=segment.text,
                start_ms=segment.start_ms + offset,
                end_ms=min(window.end_ms, segment.end_ms + offset),
                language=segment.language,
                confidence=segment.confidence,
            )
            if any(_same_occurrence(candidate, old) for old in output[-5:]):
                continue
        if output and candidate.start_ms < output[-1].start_ms:
            warnings.add("BOUNDARY_REVIEW")
            raise SpeechError(
                "Niejednoznaczne granice fragmentów; nie zapisano niechronologicznych napisów."
            )
        output.append(candidate)
    return warnings
