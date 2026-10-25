"""Cue segmentation using observed word times; no inferred internal word timings."""

import textwrap

from ai_subtitle_studio.domain.models import SubtitleCue, TranscriptSegment, WordTiming
from ai_subtitle_studio.speech.stitch import join_words


def make_cues(segments: list[TranscriptSegment]) -> tuple[list[SubtitleCue], list[str], set[str]]:
    cues, review, warnings = [], [], set()
    for segment in segments:
        width = 20 if segment.language in {"ja", "zh"} else 42
        groups: list[list[WordTiming]] = []
        current = []
        for word in segment.words:
            if current and (
                word.end_ms - current[0].start_ms > 7000
                or word.start_ms - current[-1].end_ms > 1000
                or len(join_words([*current, word], segment.language)) > width * 2
            ):
                groups.append(current)
                current = []
            current.append(word)
        if current:
            groups.append(current)
        records = [
            (
                join_words(group, segment.language),
                group[0].start_ms,
                group[-1].end_ms,
                min(
                    (w.confidence for w in group if w.confidence is not None),
                    default=segment.confidence,
                ),
            )
            for group in groups
        ]
        if not records:
            records = [(segment.text, segment.start_ms, segment.end_ms, segment.confidence)]
        for text, start, end, confidence in records:
            lines = textwrap.wrap(
                text,
                width=width,
                break_long_words=segment.language in {"ja", "zh"},
                break_on_hyphens=False,
                replace_whitespace=False,
            )
            cue = SubtitleCue(
                id=f"cue-{len(cues) + 1:06d}", text="\n".join(lines), start_ms=start, end_ms=end
            )
            cps = len(text) * 1000 / (end - start)
            if (
                (confidence is not None and confidence < 0.5)
                or len(lines) > 2
                or cps > (12 if segment.language in {"ja", "zh"} else 21)
                or end - start > 7000
            ):
                review.append(cue.id)
                warnings.add("CUE_REVIEW_REQUIRED")
            if cues and cue.start_ms < cues[-1].end_ms:
                warnings.add("OVERLAPPING_CUES")
            cues.append(cue)
    return cues, review, warnings
