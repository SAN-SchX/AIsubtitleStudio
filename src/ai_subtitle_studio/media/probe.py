"""FFprobe JSON -> validated models, preserving absolute stream indexes and PTS."""

import json
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from fractions import Fraction
from pathlib import Path
from threading import Event

from pydantic import ValidationError

from ai_subtitle_studio.config import DEFAULT_SETTINGS, VIDEO_EXTENSIONS, Settings
from ai_subtitle_studio.domain.errors import InvalidMediaError, OperationCancelled, StudioError
from ai_subtitle_studio.domain.models import AudioTrack, MediaInfo, SubtitleTrack
from ai_subtitle_studio.media.process import run_tool


def _ms(value: object) -> int | None:
    if value is None or value == "N/A":
        return None
    number = Decimal(str(value))
    if not number.is_finite():
        raise ValueError("Non-finite timestamp")
    return int((number * 1000).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def parse_probe(payload: dict) -> MediaInfo:
    try:
        streams = payload["streams"]
        container = payload.get("format", {})
        duration = _ms(container.get("duration"))
        if duration is None:
            # Unknown duration is never silently presented as zero.
            raise ValueError("Missing container duration")
        fps = None
        audio, subtitles = [], []
        for stream in streams:
            kind = stream.get("codec_type")
            tags = stream.get("tags", {})
            fields = dict(
                stream_index=stream["index"],
                language=tags.get("language"),
                title=tags.get("title"),
                codec=stream.get("codec_name"),
            )
            if kind == "audio":
                audio.append(
                    AudioTrack(
                        **fields,
                        channels=stream.get("channels"),
                        start_time_ms=_ms(stream.get("start_time")),
                    )
                )
            elif kind == "subtitle":
                subtitles.append(SubtitleTrack(**fields))
            elif (
                kind == "video"
                and fps is None
                and not stream.get("disposition", {}).get("attached_pic", 0)
            ):
                for key in ("avg_frame_rate", "r_frame_rate"):
                    value = stream.get(key)
                    if value and value != "0/0":
                        candidate = Fraction(value)
                        if candidate > 0:
                            fps = candidate
                            break
        return MediaInfo(
            duration_ms=duration,
            audio_tracks=audio,
            subtitle_tracks=subtitles,
            fps_num=fps.numerator if fps else None,
            fps_den=fps.denominator if fps else None,
            start_time_ms=_ms(container.get("start_time")),
        )
    except (
        KeyError,
        TypeError,
        ValueError,
        InvalidOperation,
        ZeroDivisionError,
        ValidationError,
        AttributeError,
    ) as exc:
        raise InvalidMediaError("Nieprawidłowe lub niepełne metadane FFprobe.") from exc


def local_video(path: Path) -> Path:
    path = Path(path).expanduser().resolve(strict=True)
    if not path.is_file() or path.suffix.lower() not in VIDEO_EXTENSIONS:
        raise InvalidMediaError("Wybierz lokalny plik MP4, MKV, MOV lub AVI.")
    return path


def probe_media(
    path: Path, settings: Settings = DEFAULT_SETTINGS, cancel: Event | None = None
) -> MediaInfo:
    try:
        path = local_video(path)
        raw = run_tool(
            [
                settings.ffprobe,
                "-v",
                "error",
                "-protocol_whitelist",
                "file,pipe",
                "-show_format",
                "-show_streams",
                "-of",
                "json",
                str(path),
            ],
            timeout_s=settings.process_timeout_s,
            cancel=cancel,
        )
        return parse_probe(json.loads(raw))
    except OperationCancelled:
        raise
    except InvalidMediaError:
        raise
    except (OSError, StudioError, ValueError) as exc:
        raise InvalidMediaError(
            "Nie można odczytać wideo. Sprawdź plik i instalację FFprobe."
        ) from exc
