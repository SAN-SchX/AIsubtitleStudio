"""Streaming 16 kHz mono PCM extraction with explicit stream and timeline mapping."""

from pathlib import Path
from threading import Event

from ai_subtitle_studio.config import DEFAULT_SETTINGS, Settings
from ai_subtitle_studio.domain.errors import InvalidMediaError
from ai_subtitle_studio.files import atomic_output
from ai_subtitle_studio.media.probe import local_video, probe_media
from ai_subtitle_studio.media.process import run_tool


def extract_audio(
    video: Path,
    output: Path,
    stream_index: int,
    *,
    settings: Settings = DEFAULT_SETTINGS,
    cancel: Event | None = None,
) -> Path:
    video = local_video(video)
    info = probe_media(video, settings, cancel)
    if not info.audio_tracks:
        raise InvalidMediaError("Wideo nie zawiera ścieżki audio.")
    if type(stream_index) is not int or stream_index not in {
        t.stream_index for t in info.audio_tracks
    }:
        raise InvalidMediaError("Wybrany strumień nie jest ścieżką audio tego pliku.")
    if output.suffix.lower() != ".wav":
        raise InvalidMediaError("Dźwięk należy zapisać jako nowy plik WAV.")
    with atomic_output(output, (video,)) as temporary:
        run_tool(
            [
                settings.ffmpeg,
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-protocol_whitelist",
                "file,pipe",
                "-copyts",
                "-start_at_zero",
                "-i",
                str(video),
                "-map",
                f"0:{stream_index}",
                "-vn",
                "-sn",
                "-dn",
                "-af",
                "aresample=16000:async=1:first_pts=0",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "pcm_s16le",
                "-f",
                "wav",
                str(temporary),
            ],
            timeout_s=settings.process_timeout_s,
            cancel=cancel,
        )
    return output
