"""Strict subtitle IO. Never flatten ASS or silently repair invalid timing."""

import codecs
import re
from dataclasses import dataclass
from pathlib import Path

import pysubs2
from pydantic import ValidationError

from ai_subtitle_studio.config import DEFAULT_SETTINGS, SUBTITLE_EXTENSIONS, Settings
from ai_subtitle_studio.domain.errors import SubtitleError
from ai_subtitle_studio.domain.models import SubtitleCue
from ai_subtitle_studio.files import atomic_output

SRT_TIME = re.compile(
    r"^(-?\d{1,6}):([0-5]\d):([0-5]\d)[,.](\d{3})\s*-->\s*"
    r"(-?\d{1,6}):([0-5]\d):([0-5]\d)[,.](\d{3})\s*$"
)
ASS_EFFECT = re.compile(r"\\(?:k[fo]?\d|K\d|t\(|move\(|fad(?:e)?\(|p[1-9])")


@dataclass(frozen=True)
class SubtitleDocument:
    source_path: Path
    format: str
    cues: tuple[SubtitleCue, ...]
    warnings: tuple[str, ...]
    _ssa: pysubs2.SSAFile  # original styles, tags, actors, comments, ordering
    _source_text: str  # preserve ASS extension sections not interpreted by pysubs2


def _decode(raw: bytes, encoding: str | None) -> str:
    try:
        if encoding is not None:
            text = raw.decode(encoding, errors="strict")
        elif raw.startswith((codecs.BOM_UTF16_LE, codecs.BOM_UTF16_BE)):
            text = raw.decode("utf-16", errors="strict")
        else:
            text = raw.decode("utf-8-sig", errors="strict")
    except (UnicodeError, LookupError) as exc:
        raise SubtitleError(
            "Niepoprawne kodowanie. Wybierz jawnie UTF-8, UTF-16 lub CP1250."
        ) from exc
    if "\x00" in text or any(ord(c) < 32 and c not in "\n\r\t" for c in text):
        raise SubtitleError("Napisy zawierają niedozwolone znaki sterujące.")
    return text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")


def _validate_srt(text: str) -> list[str]:
    blocks = re.split(r"\n[ \t]*\n", text.strip("\n"))
    if not text.strip():
        raise SubtitleError("Plik napisów jest pusty.")
    bodies = []
    for block in blocks:
        lines = block.split("\n")
        if len(lines) < 3 or not lines[0].isdigit() or not SRT_TIME.fullmatch(lines[1]):
            raise SubtitleError("Nieprawidłowy blok SRT: wymagany indeks, czas i tekst.")
        if not "\n".join(lines[2:]).strip():
            raise SubtitleError("Pusta kwestia SRT.")
        bodies.append("\n".join(lines[2:]))
    return bodies


def _validate_ass(text: str) -> None:
    section = ""
    fields = None
    expected = "layer,start,end,style,name,marginl,marginr,marginv,effect,text".split(",")
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("["):
            section = stripped
        elif section == "[Events]":
            if stripped.startswith("Format:"):
                fields = [value.strip().lower() for value in stripped.split(":", 1)[1].split(",")]
                if fields != expected:
                    raise SubtitleError("Nieobsługiwany układ kolumn zdarzeń ASS.")
            elif stripped.startswith(("Dialogue:", "Comment:")):
                values = stripped.split(":", 1)[1].split(",", 9)
                if fields is None or len(values) != 10:
                    raise SubtitleError("Nieprawidłowe zdarzenie ASS.")
                if any(
                    not re.fullmatch(r"\d+:[0-5]\d:[0-5]\d\.\d{2}", v.strip()) for v in values[1:3]
                ):
                    raise SubtitleError("Nieprawidłowy czas zdarzenia ASS.")


def load_subtitles(
    path: Path,
    *,
    encoding: str | None = None,
    settings: Settings = DEFAULT_SETTINGS,
) -> SubtitleDocument:
    path = Path(path).expanduser().resolve(strict=True)
    if path.suffix.lower() not in SUBTITLE_EXTENSIONS:
        raise SubtitleError("Obsługiwane formaty napisów: SRT i ASS.")
    with path.open("rb") as file:
        raw = file.read(settings.subtitle_limit_bytes + 1)
    if len(raw) > settings.subtitle_limit_bytes:
        raise SubtitleError("Napisy przekraczają limit 16 MiB.")
    text = _decode(raw, encoding)
    fmt = path.suffix[1:].lower()
    bodies = []
    if fmt == "srt":
        bodies = _validate_srt(text)
    elif "[Events]" not in text or "[V4+ Styles]" not in text:
        raise SubtitleError("Brak wymaganych sekcji dokumentu ASS.")
    else:
        _validate_ass(text)
    try:
        ssa = pysubs2.SSAFile.from_string(text, format_=fmt)
        if fmt == "srt" and len(ssa) != len(bodies):
            raise ValueError("SRT parser did not retain all blocks")
        cues = []
        warnings = set()
        previous = -1
        for index, event in enumerate(ssa):
            # Include comments as document metadata, not spoken cues.
            if event.start < 0 or event.end <= event.start:
                raise ValueError("Invalid event timing")
            if event.is_comment:
                continue
            cues.append(
                SubtitleCue(
                    id=f"cue-{index + 1:06d}",
                    text=bodies[index] if fmt == "srt" else event.text,
                    start_ms=event.start,
                    end_ms=event.end,
                    original_start_ms=event.start,
                    original_end_ms=event.end,
                    style=event.style,
                )
            )
            if event.start < previous:
                warnings.add("UNSORTED_CUES")
            previous = event.start
            if ASS_EFFECT.search(event.text) or event.effect:
                warnings.add("ASS_EFFECTS_UNVERIFIED")
        if not cues:
            raise ValueError("No dialogue cues")
        return SubtitleDocument(path, fmt, tuple(cues), tuple(sorted(warnings)), ssa, text)
    except (ValueError, ValidationError, pysubs2.Pysubs2Error) as exc:
        raise SubtitleError("Nieprawidłowe napisy: sprawdź czasy i treść kwestii.") from exc


def export_subtitles(document: SubtitleDocument, output: Path) -> Path:
    output = Path(output)
    if output.suffix.lower() != f".{document.format}":
        raise SubtitleError("Zapisz w formacie źródłowym. Konwersja ASS/SRT nie jest obsługiwana.")
    # Keep style/event metadata intact; no retiming/editing in phases 0–1.
    if document.format == "srt":
        # pysubs2's ASS intermediary strips some SRT HTML/literal braces. Keep
        # validated source text separately, emitting conventional SRT indexes.
        def timestamp(ms: int) -> str:
            seconds, milliseconds = divmod(ms, 1000)
            minutes, seconds = divmod(seconds, 60)
            hours, minutes = divmod(minutes, 60)
            return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

        text = "".join(
            f"{index}\n{timestamp(cue.start_ms)} --> {timestamp(cue.end_ms)}\n{cue.text}\n\n"
            for index, cue in enumerate(document.cues, 1)
        )
    else:
        # Phase 1 only exports copies. Preserve even extension sections that the
        # parser cannot model; later retiming needs a separate fidelity contract.
        text = document._source_text
    data = text.encode("utf-8")
    with atomic_output(output, (document.source_path,)) as temporary:
        temporary.write_bytes(data)
    return output
