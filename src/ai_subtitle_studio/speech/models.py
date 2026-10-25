"""Model management: fixed presets, local-only inference, explicit download consent."""

import importlib.metadata
import json
import os
import platform
from pathlib import Path

from ai_subtitle_studio.speech.base import SpeechError

MLX_WHISPER_VERSION = "0.4.3"
PRESETS = {
    "speed": "mlx-community/whisper-small-mlx",
    "accurate": "mlx-community/whisper-large-v3-turbo",
}


def model_root() -> Path:
    return Path.home() / "Library" / "Application Support" / "AI Subtitle Studio" / "models"


def preset_path(preset: str) -> Path:
    return model_root() / PRESETS[preset].split("/")[1]


def validate_model(directory: Path) -> Path:
    path = directory.expanduser().resolve()
    if not (path / "config.json").is_file() or not any(
        (path / name).is_file() and (path / name).stat().st_size > 0
        for name in ("weights.safetensors", "weights.npz")
    ):
        raise SpeechError(
            "Brak lokalnego modelu MLX (config.json i weights.safetensors/weights.npz). "
            "Wybierz katalog lub pobierz model jawną komendą download-model --accept-download."
        )
    try:
        if (path / "config.json").stat().st_size > 1024 * 1024:
            raise ValueError("Oversized config")
        data = json.loads((path / "config.json").read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not {"n_mels", "n_vocab"} <= data.keys():
            raise ValueError()
    except (ValueError, OSError) as exc:
        raise SpeechError("Nieprawidłowy config.json lokalnego modelu Whisper MLX.") from exc
    return path


def backend_problem() -> str | None:
    if platform.system() != "Darwin" or platform.machine() != "arm64":
        return "Transkrypcja MLX wymaga macOS na Apple Silicon (arm64)."
    try:
        if importlib.metadata.version("mlx-whisper") != MLX_WHISPER_VERSION:
            return "Wymagana wersja mlx-whisper 0.4.3. Uruchom uv sync --frozen --extra speech."
        importlib.metadata.version("mlx")
    except importlib.metadata.PackageNotFoundError:
        return "Brak backendu MLX. Uruchom uv sync --frozen --extra speech na Macu arm64."
    return None


def readiness(directory: Path) -> str | None:
    problem = backend_problem()
    if problem:
        return problem
    try:
        validate_model(directory)
    except (SpeechError, OSError) as exc:
        return str(exc)
    return None


def download_model(preset: str, destination: Path, *, consent: bool = False) -> Path:
    if not consent:
        raise SpeechError(
            "Pobranie modelu wymaga jawnej zgody: dodaj --accept-download. "
            "Model może zajmować kilka GB; pobieranie kontaktuje się z Hugging Face."
        )
    if preset not in PRESETS:
        raise SpeechError("Nieznany wariant modelu.")
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SpeechError(
            "Zainstaluj opcjonalne zależności: uv sync --frozen --extra speech."
        ) from exc
    destination = destination.expanduser().resolve()
    # A ready directory is reused without a network call. Do not replace user models.
    if destination.exists():
        try:
            return validate_model(destination)
        except SpeechError as exc:
            raise SpeechError(
                "Folder już istnieje, lecz model jest niekompletny. Wybierz nowy folder."
            ) from exc
    # Only model assets, no executable repository code and no user data upload.
    try:
        snapshot_download(
            repo_id=PRESETS[preset],
            local_dir=str(destination),
            allow_patterns=["config.json", "weights.safetensors", "weights.npz"],
        )
    except Exception as exc:
        raise SpeechError(
            "Pobranie nie powiodło się. Sprawdź sieć i dostęp do Hugging Face; "
            "nie wyłączaj weryfikacji TLS. Niekompletny katalog nie jest używany do ASR."
        ) from exc
    return validate_model(destination)
