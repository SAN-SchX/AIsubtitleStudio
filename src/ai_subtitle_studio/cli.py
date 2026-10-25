"""CLI with lazy GUI import so doctor works without a display."""

import argparse
import logging
from pathlib import Path


def _stream_index(text: str) -> int:
    value = int(text)
    if value < 0:
        raise argparse.ArgumentTypeError("Indeks ścieżki nie może być ujemny")
    return value


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Subtitle Studio — lokalne wideo i napisy")
    parser.add_argument(
        "command",
        nargs="?",
        choices=["gui", "doctor", "transcribe", "download-model"],
        default="gui",
    )
    parser.add_argument("--json", action="store_true", help="Wynik diagnostyki w JSON")
    parser.add_argument("--no-ollama", action="store_true", help="Pomiń lokalną Ollamę w doctor")
    parser.add_argument("--log", action="store_true", help="Włącz logowanie bez treści dialogów")
    parser.add_argument("--smoke-test", action="store_true", help="Otwórz GUI i zamknij po 250 ms")
    parser.add_argument("--video", type=Path, help="Lokalny plik wideo do transkrypcji")
    parser.add_argument(
        "--audio-stream", type=_stream_index, help="Absolutny indeks ścieżki audio z FFprobe"
    )
    parser.add_argument("--language", choices=["auto", "pl", "en", "ja"], default="auto")
    parser.add_argument("--preset", choices=["speed", "accurate"], default="speed")
    parser.add_argument("--model-dir", type=Path, help="Katalog istniejącego lokalnego modelu MLX")
    parser.add_argument("--output", type=Path, help="Nowy plik SRT (bez nadpisywania)")
    parser.add_argument(
        "--accept-download", action="store_true", help="Jawna zgoda na pobranie modelu"
    )
    parser.add_argument(
        "--check-speech", action="store_true", help="Wymagaj MLX i lokalnego modelu w doctor"
    )
    args = parser.parse_args(argv)
    if args.log:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        logging.getLogger(__name__).info("Uruchomiono aplikację; bez danych dialogowych")
    if args.command == "doctor":
        from ai_subtitle_studio.doctor import checks_json, diagnose

        checks = diagnose(
            check_ollama=not args.no_ollama,
            check_speech=args.check_speech,
            model_dir=args.model_dir,
        )
        if args.json:
            print(checks_json(checks))
        else:
            for check in checks:
                status = "OK" if check.ok else ("BRAK" if check.required else "UWAGA")
                print(f"[{status}] {check.name}: {check.detail}")
        return int(any(check.required and not check.ok for check in checks))
    if args.command in {"transcribe", "download-model"}:
        from ai_subtitle_studio.domain.errors import StudioError
        from ai_subtitle_studio.domain.models import JobConfig
        from ai_subtitle_studio.jobs.transcribe import transcribe_video
        from ai_subtitle_studio.speech.mlx_whisper import MlxSpeechProvider
        from ai_subtitle_studio.speech.models import download_model, preset_path

        directory = args.model_dir or preset_path(args.preset)
        try:
            if args.command == "download-model":
                download_model(args.preset, directory, consent=args.accept_download)
                print("Lokalny model jest gotowy. Nie uruchomiono transkrypcji.")
                return 0
            if args.video is None or args.audio_stream is None or args.output is None:
                parser.error("transcribe wymaga --video, --audio-stream i --output")
            config = JobConfig(
                video_path=args.video,
                mode="transcribe",
                audio_stream_index=args.audio_stream,
                source_language=None if args.language == "auto" else args.language,
            )
            result = transcribe_video(config, args.output, MlxSpeechProvider(directory))
            print(result.summary)
            print("Ostrzeżenia: " + ", ".join(result.warnings))
            return 0
        except (StudioError, OSError) as exc:
            print(f"Błąd: {exc}")
            return 1
        except KeyboardInterrupt:
            print("Operacja przerwana; procesy i pliki tymczasowe zamknięte.")
            return 130
    from ai_subtitle_studio.gui.app import run

    return run(smoke_test=args.smoke_test)
