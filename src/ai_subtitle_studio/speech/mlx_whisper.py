"""Persistent local MLX subprocess; killing it cancels inference and releases its model."""

import json
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path
from threading import Event

from pydantic import ValidationError

from ai_subtitle_studio.speech.base import SpeechError, SpeechResult, check_cancel
from ai_subtitle_studio.speech.models import MLX_WHISPER_VERSION, backend_problem, validate_model


class MlxSpeechProvider:
    def __init__(self, model_dir: Path, *, timeout_s: float = 300):
        problem = backend_problem()
        if problem:
            raise SpeechError(problem)
        self.model_dir = validate_model(model_dir)
        self.model_id = f"{self.model_dir.name} / mlx-whisper {MLX_WHISPER_VERSION}"
        self.timeout_s = timeout_s
        self._work = tempfile.TemporaryDirectory(prefix="aisub-mlx-")
        self._process: subprocess.Popen | None = None
        self._sequence = 0
        self._closed = False

    def _command(self) -> list[str]:
        return [
            sys.executable,
            "-m",
            "ai_subtitle_studio.speech.mlx_worker",
            "--model-dir",
            str(self.model_dir),
            "--work-dir",
            self._work.name,
        ]

    def _start(self) -> None:
        if self._closed:
            raise SpeechError("Backend został już zamknięty.")
        if self._process is None:
            environment = os.environ.copy()
            environment.update(
                HF_HUB_OFFLINE="1",
                TRANSFORMERS_OFFLINE="1",
                HF_HUB_DISABLE_TELEMETRY="1",
                DO_NOT_TRACK="1",
            )
            self._process = subprocess.Popen(
                self._command(),
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                shell=False,
                env=environment,
            )

    def transcribe(self, wav: Path, *, language: str | None, cancel: Event) -> SpeechResult:
        check_cancel(cancel)
        self._start()
        self._sequence += 1
        response = Path(self._work.name) / f"response-{self._sequence}.json"
        request = (
            json.dumps(
                {
                    "sequence": self._sequence,
                    "wav": str(wav.resolve(strict=True)),
                    "language": language,
                }
            ).encode()
            + b"\n"
        )
        try:
            self._process.stdin.write(request)
            self._process.stdin.flush()
            deadline = time.monotonic() + self.timeout_s
            while not response.exists():
                check_cancel(cancel)
                if self._process.poll() is not None:
                    raise SpeechError(
                        "Proces MLX zakończył się błędem. Sprawdź model i zależności."
                    )
                if time.monotonic() >= deadline:
                    raise SpeechError("Przekroczono limit czasu transkrypcji fragmentu.")
                cancel.wait(0.05)
            check_cancel(cancel)
            if response.stat().st_size > 4 * 1024 * 1024:
                raise SpeechError("Zbyt duża odpowiedź backendu MLX.")
            data = json.loads(response.read_text(encoding="utf-8"))
            if "error" in data:
                if data["error"] == "out_of_memory":
                    raise SpeechError(
                        "Brak pamięci dla modelu. Wybierz wariant szybki i zamknij inne modele."
                    )
                raise SpeechError("Backend MLX nie przetworzył fragmentu. Sprawdź lokalny model.")
            return SpeechResult.model_validate(data)
        except (BrokenPipeError, ValueError, ValidationError) as exc:
            self.close()
            raise SpeechError("Nieprawidłowa odpowiedź procesu MLX.") from exc
        except BaseException:
            self.close()
            raise
        finally:
            response.unlink(missing_ok=True)

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        try:
            if self._process is not None:
                if self._process.stdin:
                    try:
                        self._process.stdin.close()
                    except OSError:
                        pass
                if self._process.poll() is None:
                    self._process.terminate()
                    try:
                        self._process.wait(timeout=1)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                        self._process.wait()
        finally:
            self._work.cleanup()
