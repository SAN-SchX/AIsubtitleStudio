# Instalacja na macOS / Apple Silicon

**Status:** procedura przygotowana, lecz nie wykonana na MacBooku Air M5.
Nie ma jeszcze pakietu `.app`, podpisu ani notaryzacji. Nie instaluj Rosetty
ani wersji x86_64 Pythona do tego projektu. Koła PySide6 w lockfile są universal2,
Pydantic ma wariant arm64; ich uruchomienie na docelowym Macu wymaga weryfikacji.
PySide6 6.10.1 wymaga macOS 13 lub nowszego.

## Wymagania

- Python **3.12**, `uname -m` → `arm64`.
- `uv` (menedżer pakietów Astral) lub standardowy `venv`.
- FFmpeg i FFprobe w PATH, np. `brew install ffmpeg` przy zainstalowanym Homebrew.
- Dostęp do internetu wyłącznie podczas instalacji pakietów. Żaden model nie
  jest potrzebny ani pobierany w fazie 1. Ollama jest opcjonalna.

W istniejącym checkout (bez tworzenia worktree):

```bash
uname -m
python3.12 -c 'import platform; print(platform.machine())'
ffmpeg -version
ffprobe -version
uv sync --frozen --python python3.12
uv run --frozen python scripts/doctor.py
uv run --frozen python -m ai_subtitle_studio
```

Nie ustawiaj `QT_QPA_PLATFORM=offscreen` przy normalnym użyciu na Macu.
To tryb testowy dla chmury bez ekranu. Uruchamiaj GUI z sesji zalogowanego użytkownika.

## Alternatywa bez uv

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -e .
python scripts/doctor.py
python -m ai_subtitle_studio
```

Wariant `uv sync --frozen` jest preferowany: respektuje cały lockfile wraz z hashami.
Wariant pip respektuje przypięte zależności bez pełnego zamrożenia przechodniego.

## Odbiór ręczny na Macu — do wykonania

- Otworzyć okno, przeciągnąć wideo ze ścieżką Unicode z Findera i przez dialog.
- Zweryfikować klawiaturę, skalowanie okna i wybór PL/EN/JA.
- Na lokalnym filmie z kilkoma ścieżkami sprawdzić właściwy dubbing w zapisanym WAV.
- Zaimportować SRT i ASS, zapisać kopię, porównać tekst i style; sprawdzić odmowę nadpisania.
- Anulować ekstrakcję i zamknąć okno; sprawdzić brak procesu FFmpeg w tle.
- Uruchomić `uv run --frozen pytest -q` (bez pominięć, z FFmpeg).

Realna transkrypcja, wydajność MLX i pomiar zużycia 16 GB RAM wymagają fazy 2.
Nie pobieraj modeli „na zapas” w celu uruchomienia tej wersji.
