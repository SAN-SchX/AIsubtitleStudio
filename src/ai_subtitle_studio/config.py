"""Small local configuration; no network endpoints accepted from media files."""

from dataclasses import dataclass

VIDEO_EXTENSIONS = frozenset({".mp4", ".mkv", ".mov", ".avi"})
SUBTITLE_EXTENSIONS = frozenset({".srt", ".ass"})
LANGUAGES = (("Automatycznie", None), ("Polski", "pl"), ("Angielski", "en"), ("Japoński", "ja"))


@dataclass(frozen=True)
class Settings:
    ffprobe: str = "ffprobe"
    ffmpeg: str = "ffmpeg"
    process_timeout_s: float = 60.0
    subtitle_limit_bytes: int = 16 * 1024 * 1024


DEFAULT_SETTINGS = Settings()
