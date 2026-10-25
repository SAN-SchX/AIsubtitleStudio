"""Canonical contracts. Models are frozen; callers replace rather than mutate them."""

from pathlib import Path
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

Milliseconds = Annotated[int, Field(strict=True, ge=0)]
StreamIndex = Annotated[int, Field(strict=True, ge=0)]
Identifier = Annotated[str, Field(min_length=1, pattern=r"\S")]
Confidence = Annotated[float, Field(ge=0, le=1, allow_inf_nan=False)]


class DomainModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")


class AudioTrack(DomainModel):
    stream_index: StreamIndex
    language: str | None = None
    title: str | None = None
    codec: str | None = None
    channels: Annotated[int, Field(strict=True, gt=0)] | None = None
    start_time_ms: int | None = None  # signed PTS, not a subtitle time


class SubtitleTrack(DomainModel):
    stream_index: StreamIndex
    language: str | None = None
    title: str | None = None
    codec: str | None = None


class MediaInfo(DomainModel):
    duration_ms: Milliseconds
    audio_tracks: list[AudioTrack] = Field(default_factory=list)
    subtitle_tracks: list[SubtitleTrack] = Field(default_factory=list)
    fps_num: Annotated[int, Field(strict=True, gt=0)] | None = None
    fps_den: Annotated[int, Field(strict=True, gt=0)] | None = None
    start_time_ms: int | None = None

    @model_validator(mode="after")
    def validate_streams(self) -> Self:
        if (self.fps_num is None) != (self.fps_den is None):
            raise ValueError("FPS requires numerator and denominator")
        indexes = [t.stream_index for t in [*self.audio_tracks, *self.subtitle_tracks]]
        if len(indexes) != len(set(indexes)):
            raise ValueError("Stream indexes must be unique")
        return self


class TimedSpan(DomainModel):
    start_ms: Milliseconds
    end_ms: Milliseconds

    @model_validator(mode="after")
    def validate_interval(self) -> Self:
        if self.end_ms <= self.start_ms:
            raise ValueError("Required: 0 <= start_ms < end_ms")
        return self


class WordTiming(TimedSpan):
    text: str
    confidence: Confidence | None = None


class TranscriptSegment(TimedSpan):
    id: Identifier
    text: str
    language: str
    words: list[WordTiming] = Field(default_factory=list)
    confidence: Confidence | None = None


class SubtitleCue(TimedSpan):
    id: Identifier
    text: Annotated[str, Field(min_length=1)]
    original_start_ms: Milliseconds | None = None
    original_end_ms: Milliseconds | None = None
    style: str | None = None

    @model_validator(mode="after")
    def validate_original(self) -> Self:
        if not self.text.strip():
            raise ValueError("Subtitle text must not be blank")
        if (self.original_start_ms is None) != (self.original_end_ms is None):
            raise ValueError("Original timing requires both endpoints")
        if self.original_start_ms is not None and self.original_end_ms <= self.original_start_ms:
            raise ValueError("Original end must follow original start")
        return self


class AlignmentPair(DomainModel):
    subtitle_ids: list[Identifier]
    transcript_ids: list[Identifier]
    score: Confidence
    status: Literal["matched", "review", "unmatched"]
    reasons: list[str] = Field(default_factory=list)


class JobConfig(DomainModel):
    video_path: Path
    subtitle_path: Path | None = None
    mode: Literal["inspect", "synchronize", "transcribe", "transcribe_translate", "translate"]
    audio_stream_index: StreamIndex | None = None
    source_language: str | None = None
    target_language: str | None = None
    quality_preset: Literal["memory_safe", "speed", "accurate"] = "memory_safe"
    model_id: str | None = None
    output_dir: Path | None = None


class JobResult(DomainModel):
    output_paths: list[Path] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    low_confidence_cue_ids: list[Identifier] = Field(default_factory=list)
    metrics: dict[str, float] = Field(default_factory=dict)
    summary: str
