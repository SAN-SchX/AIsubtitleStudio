"""Bounded subprocess execution; stdout on disk avoids unbounded RAM use."""

import subprocess
import tempfile
import time
from threading import Event

from ai_subtitle_studio.domain.errors import OperationCancelled, StudioError


def run_tool(argv: list[str], *, timeout_s: float, cancel: Event | None = None) -> bytes:
    if cancel is not None and cancel.is_set():
        raise OperationCancelled("Operacja anulowana.")
    with tempfile.TemporaryFile() as output:
        try:
            process = subprocess.Popen(
                argv,
                stdin=subprocess.DEVNULL,
                stdout=output,
                stderr=subprocess.DEVNULL,
                shell=False,
            )
        except FileNotFoundError as exc:
            raise StudioError("Brak programu FFmpeg/FFprobe. Uruchom diagnostykę doctor.") from exc
        try:
            deadline = time.monotonic() + timeout_s
            while process.poll() is None:
                if cancel is not None and cancel.is_set():
                    raise OperationCancelled("Operacja anulowana.")
                if time.monotonic() >= deadline:
                    raise StudioError("Przekroczono limit czasu programu multimedialnego.")
                try:
                    process.wait(timeout=0.05)
                except subprocess.TimeoutExpired:
                    pass
            if cancel is not None and cancel.is_set():
                raise OperationCancelled("Operacja anulowana.")
            if process.returncode != 0:
                raise StudioError("Program multimedialny odrzucił plik lub strumień.")
            if output.tell() > 8 * 1024 * 1024:
                raise StudioError("Zbyt duży wynik programu multimedialnego.")
            output.seek(0)
            return output.read()
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=1)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait()
