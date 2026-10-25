"""Read-only diagnostics; no downloads, no environment dumps, loopback only."""

import importlib.metadata
import json
import platform
import sys
from dataclasses import asdict, dataclass
from http.client import HTTPConnection, HTTPException
from pathlib import Path

from ai_subtitle_studio.config import DEFAULT_SETTINGS, Settings
from ai_subtitle_studio.domain.errors import StudioError
from ai_subtitle_studio.media.process import run_tool


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    required: bool
    detail: str


def ollama_models(timeout_s: float = 1.0) -> set[str]:
    connection = HTTPConnection("127.0.0.1", 11434, timeout=timeout_s)
    try:
        connection.request("GET", "/api/tags")
        response = connection.getresponse()
        if response.status != 200:
            raise ValueError("Ollama did not return 200")
        raw = response.read(1024 * 1024 + 1)
        if len(raw) > 1024 * 1024:
            raise ValueError("Oversized Ollama response")
        data = json.loads(raw)
        return {model["name"] for model in data["models"]}
    finally:
        connection.close()


def diagnose(
    settings: Settings = DEFAULT_SETTINGS,
    *,
    check_ollama: bool = True,
    check_speech: bool = False,
    model_dir: Path | None = None,
) -> list[Check]:
    checks = [
        Check("Python 3.12", sys.version_info[:2] == (3, 12), True, platform.python_version()),
        Check(
            "macOS Apple Silicon",
            platform.system() == "Darwin" and platform.machine() == "arm64",
            False,
            f"{platform.system()} {platform.machine()} — natywne testy wymagają Maca",
        ),
    ]
    for package in ("PySide6", "pysubs2", "pydantic"):
        try:
            checks.append(Check(package, True, True, importlib.metadata.version(package)))
        except importlib.metadata.PackageNotFoundError:
            checks.append(Check(package, False, True, "Zainstaluj zależności: uv sync --frozen"))
    for name, executable in (("FFmpeg", settings.ffmpeg), ("FFprobe", settings.ffprobe)):
        try:
            version = run_tool([executable, "-version"], timeout_s=5).decode().splitlines()[0]
            checks.append(Check(name, True, True, version))
        except (StudioError, OSError, UnicodeError, IndexError):
            checks.append(
                Check(name, False, True, "Brak lub błąd programu; na Macu: brew install ffmpeg")
            )
    if check_ollama:
        try:
            models = ollama_models()
            checks.append(Check("Ollama", True, False, "Lokalna usługa odpowiada"))
            for model in ("qwen3:4b", "qwen3-embedding:0.6b"):
                checks.append(
                    Check(
                        model,
                        model in models,
                        False,
                        "Dostępny" if model in models else "Niepobrany; potrzebny w fazach 4–5",
                    )
                )
        except (OSError, ValueError, KeyError, TypeError, HTTPException):
            checks.append(
                Check(
                    "Ollama",
                    False,
                    False,
                    "Usługa niedostępna; opcjonalna w fazie 1. Nie pobrano modeli.",
                )
            )
    else:
        checks.append(Check("Ollama", False, False, "Pominięto sprawdzanie usługi"))
    from ai_subtitle_studio.speech.models import backend_problem, preset_path, readiness

    problem = readiness(model_dir or preset_path("speed")) if check_speech else backend_problem()
    checks.append(
        Check(
            "MLX Whisper",
            problem is None,
            check_speech,
            problem
            or (
                "Backend i lokalny model dostępne"
                if check_speech
                else "Backend dostępny; model: doctor --check-speech"
            ),
        )
    )
    return checks


def checks_json(checks: list[Check]) -> str:
    return json.dumps([asdict(check) for check in checks], ensure_ascii=False, indent=2)
