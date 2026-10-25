# AI Subtitle Studio

Lokalna aplikacja desktopowa do pracy z wideo i napisami. Docelowo: macOS,
Apple Silicon, 16 GB RAM, Python 3.12. Interfejs jest po polsku.

**Stan 0.2.0:** fazy 0–1 zweryfikowano na Linuksie. Dodano implementację fazy 2
(adapter MLX, pipeline i GUI); **rzeczywista transkrypcja na Macu pozostaje
NOT VERIFIED**. Testy z kontrolowanym providerem nie są dowodem jakości Whispera.

Dostępne funkcje:

- import lokalnego MP4/MKV/MOV/AVI oraz SRT/ASS przez dialog i drag/drop;
- czas, FPS, ścieżki audio i napisów przez FFprobe;
- jawny wybór audio, języka PL/EN/JA lub auto; ekstrakcja WAV 16 kHz mono;
- podgląd pierwszych 500 kwestii i zapis całej kopii SRT/ASS UTF-8;
- odmowa nadpisywania, także linków i plików utworzonych w trakcie zapisu;
- na Macu z zainstalowanym backendem i lokalnym modelem: przycisk transkrypcji,
  przetwarzanie oknami, postęp rzeczywistych fragmentów i anulowanie;
- diagnostyka lokalnych zależności bez pobierania modeli.

Synchronizacja, tłumaczenie, edytor i podgląd wideo pozostają „Planowane”.

## Instalacja i start

Python 3.12, `uv` oraz FFmpeg/FFprobe w PATH. W istniejącym katalogu repozytorium:

```bash
uv sync --frozen
uv run --frozen python scripts/doctor.py
uv run --frozen python -m ai_subtitle_studio
```

Na Macu arm64 dla fazy 2 doinstaluj opcjonalne zależności:

```bash
uv sync --frozen --extra speech
```

Ta komenda nie pobiera modeli. W GUI wybierz katalog modelu zawierający
`config.json` i `weights.safetensors` lub `weights.npz`. Niekompletny model,
brak zależności albo niewspierany system blokują przycisk transkrypcji.
Jawne pobranie modelu i polecenie CLI: [docs/phase2.md](docs/phase2.md).
Instalacja na Macu: [docs/install_macos.md](docs/install_macos.md).

Ollama **nie jest potrzebna do transkrypcji**. `doctor` może sprawdzić wyłącznie
lokalne `127.0.0.1:11434/api/tags`; `--no-ollama` pomija nawet to połączenie.
`doctor --check-speech --model-dir /ścieżka/do/modelu` wymaga MLX i lokalnych wag.

## Pliki i prywatność

Oryginały nie są otwierane do zapisu. Kopiowanie napisów zachowuje format źródłowy;
konwersja ASS↔SRT jest blokowana. SRT zachowuje oryginalny tekst, ASS również
sekcje nieinterpretowane przez parser. Efekty ASS nie mają gwarancji renderowania
ani retimingu; aplikacja ostrzega o karaoke/animacji/rysunkach.

UTF-8/BOM i UTF-16 z BOM są rozpoznawane. CP1250 wybierz przed otwarciem starego
polskiego pliku. Błędne kodowanie nie jest zgadywane. Napisy: do 16 MiB.

Aplikacja nie wysyła filmów, audio ani transkrypcji na serwery. Nie ma telemetrii
aplikacji. Logowanie jest domyślnie wyłączone (`--log` włącza metadane bez dialogów).
Instalacja pakietów i **jawne** pobranie modeli wymagają internetu. ASR dostaje
wyłącznie lokalny katalog, z włączonym trybem offline Hugging Face.

## Testy i ograniczenia

```bash
uv run --frozen pytest -q
uv run --frozen ruff check .
uv run --frozen ruff format --check .
```

Na maszynie bez ekranu:

```bash
QT_QPA_PLATFORM=offscreen uv run --frozen pytest -q
QT_QPA_PLATFORM=offscreen uv run --frozen python -m ai_subtitle_studio --smoke-test
```

Testy podstawowe działają bez modeli i sieci. Integracje mediów wymagają lokalnego
FFmpeg/FFprobe. Trzy testy prawdziwego MLX wymagają Maca i własnego korpusu mowy —
przy braku tych warunków są jawnie pomijane. Korpus w repo zawiera własne teksty,
kolor i tony, nie rzeczywiste nagrania PL/EN/JA.

Filtr amplitudy wycina ciszę, lecz **nie jest Silero VAD** i nie rozpoznaje muzyki.
Dedupikacja na granicach jest konserwatywna i wymaga sprawdzenia na realnej mowie.
Nie zweryfikowano zużycia pamięci ani jakości na MacBooku Air M5.

[Wyniki testów faz 0–1](docs/validation.md) · [Faza 2](docs/phase2.md) ·
[Zmienione pliki](docs/files.md) · [TASKS.md](TASKS.md) · [CHANGELOG.md](CHANGELOG.md) ·
[ROADMAP.md](ROADMAP.md) · [Architektura](docs/architecture.md) · [ADR](docs/decisions.md)
