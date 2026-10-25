"""Atomic publication with no overwrite, including races and dangling symlinks."""

import os
import re
import tempfile
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from threading import Event

from ai_subtitle_studio.domain.errors import OperationCancelled, OutputConflictError, StudioError


def output_target(path: Path, sources: tuple[Path, ...] = ()) -> Path:
    # Resolve the parent, not the final component: a dangling symlink is a conflict too.
    path = Path(path).expanduser()
    target = path.parent.resolve(strict=True) / path.name
    if target.exists() or target.is_symlink():
        raise OutputConflictError("Plik wyjściowy już istnieje. Wybierz nową nazwę.")
    for source in sources:
        if target == source.resolve():
            raise OutputConflictError("Nie można zastąpić pliku źródłowego.")
    return target


@contextmanager
def atomic_output(
    path: Path, sources: tuple[Path, ...] = (), *, cancel: Event | None = None
) -> Iterator[Path]:
    """Yield a private temp file; publish only on success, never replace a directory entry."""
    target = output_target(path, sources)
    descriptor, name = tempfile.mkstemp(prefix=".aisub-", suffix=target.suffix, dir=target.parent)
    os.close(descriptor)
    temporary = Path(name)
    try:
        yield temporary
        with temporary.open("rb") as file:
            os.fsync(file.fileno())
        if cancel is not None and cancel.is_set():
            raise OperationCancelled("Zapis anulowany.")
        try:
            os.link(temporary, target)
        except FileExistsError as exc:
            raise OutputConflictError("Plik powstał podczas zapisu. Wybierz nową nazwę.") from exc
        except OSError as exc:
            raise StudioError("Nie można bezpiecznie zapisać pliku w tym folderze.") from exc
    finally:
        temporary.unlink(missing_ok=True)


def sidecar_path(video: Path, language: str, suffix: str = ".srt") -> Path:
    if not re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})*", language):
        raise ValueError("Invalid language code")
    if suffix not in {".srt", ".ass"}:
        raise ValueError("Unsupported subtitle format")
    return video.with_name(f"{video.stem}.{language}{suffix}")
