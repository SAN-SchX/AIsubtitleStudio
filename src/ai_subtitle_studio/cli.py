"""CLI with lazy GUI import so doctor works without a display."""

import argparse
import logging


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI Subtitle Studio — lokalne wideo i napisy")
    parser.add_argument("command", nargs="?", choices=["gui", "doctor"], default="gui")
    parser.add_argument("--json", action="store_true", help="Wynik diagnostyki w JSON")
    parser.add_argument("--no-ollama", action="store_true", help="Pomiń lokalną Ollamę w doctor")
    parser.add_argument("--log", action="store_true", help="Włącz logowanie bez treści dialogów")
    parser.add_argument("--smoke-test", action="store_true", help="Otwórz GUI i zamknij po 250 ms")
    args = parser.parse_args(argv)
    if args.log:
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
        logging.getLogger(__name__).info("Uruchomiono aplikację; bez danych dialogowych")
    if args.command == "doctor":
        from ai_subtitle_studio.doctor import checks_json, diagnose

        checks = diagnose(check_ollama=not args.no_ollama)
        if args.json:
            print(checks_json(checks))
        else:
            for check in checks:
                status = "OK" if check.ok else ("BRAK" if check.required else "UWAGA")
                print(f"[{status}] {check.name}: {check.detail}")
        return int(any(check.required and not check.ok for check in checks))
    from ai_subtitle_studio.gui.app import run

    return run(smoke_test=args.smoke_test)
