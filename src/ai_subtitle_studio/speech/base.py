from collections.abc import Callable
from pathlib import Path
from threading import Event
from typing import Protocol, Self

from pydantic import Field, model_validator

from ai_subtitle_studio.domain.errors import OperationCancelled, StudioError
from ai_subtitle_studio.domain.models import DomainModel, TranscriptSegment


class SpeechError(StudioError):
    """A safe, actionable ASR failure without source dialogue."""


class SpeechResult(DomainModel):
    language: str = Field(pattern=r"^[a-z]{2,3}$")
    segments: list[TranscriptSegment]
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def consistent_language(self) -> Self:
        if any(segment.language != self.language for segment in self.segments):
            raise ValueError("Inconsistent segment language")
        return self


class StageProgress(DomainModel):
    stage: str
    completed: int = Field(default=0, ge=0)
    total: int = Field(default=0, ge=0)


ProgressCallback = Callable[[StageProgress], None]


class SpeechProvider(Protocol):
    model_id: str

    def transcribe(self, wav: Path, *, language: str | None, cancel: Event) -> SpeechResult: ...

    def close(self) -> None: ...


def check_cancel(cancel: Event) -> None:
    if cancel.is_set():
        raise OperationCancelled("Transkrypcja anulowana.")
