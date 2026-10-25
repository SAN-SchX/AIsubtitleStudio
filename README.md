# AI Subtitle Studio

Lokalna aplikacja desktopowa do pracy z wideo i napisami. **Zaimplementowane:
fazy 0 i 1.** Interfejs jest po polsku. Docelowo: macOS, Apple Silicon,
16 GB RAM, Python 3.12. Bieżące testy wykonano na Linuksie x86_64.

Działa już:

- wybór i przeciąganie lokalnego MP4/MKV/MOV/AVI oraz SRT/ASS;
- FFprobe: czas, racjonalny FPS, wszystkie ścieżki audio i napisów;
- jawny wybór audio i języka źródłowego: auto / polski / angielski / japoński;
- zapis wybranej ścieżki jako PCM WAV, 16 kHz mono, z zachowaniem jej opóźnienia;
- import SRT/ASS, podgląd pierwszych 500 kwestii i eksport całej kopii UTF-8;
- ochrona istniejących plików, w tym linków i konfliktu powstałego w trakcie zapisu;
- praca plikowa poza wątkiem GUI, anulowanie FFprobe/FFmpeg i diagnostyka `doctor`.

**Jeszcze nie działa:** transkrypcja MLX, synchronizacja, wykrywanie skoków opóźnienia,
tłumaczenie Ollamą, edycja i podgląd wideo. Przyciski tych trybów są wyłączone
z etykietą „Planowane”. Nie ma przykładowej transkrypcji udającej wynik modelu.

## Instalacja i uruchomienie

W katalogu repozytorium, z Pythonem 3.12, `uv` i FFmpeg/FFprobe w PATH:

```bash
uv sync --frozen
uv run --frozen python scripts/doctor.py
uv run --frozen python -m ai_subtitle_studio
```

Ollama i modele **nie są wymagane w fazie 1**. `doctor` sprawdza wyłącznie
lokalne `127.0.0.1:11434/api/tags`; brak usługi/modeli jest ostrzeżeniem,
nie błędem obecnej aplikacji. Żadne modele nie są automatycznie pobierane.
`doctor --no-ollama` pomija nawet to lokalne połączenie.

Instrukcja macOS i alternatywa `venv`: [docs/install_macos.md](docs/install_macos.md).

## Użycie

1. Otwórz wideo albo upuść je na okno. Przeczytaj metadane.
2. Wybierz konkretną ścieżkę audio. Aplikacja nie zgaduje właściwego dubbingu.
3. Opcjonalnie wybierz język. Ten wybór trafia do konfiguracji zadania; nie uruchamia ASR.
4. „Zapisz wybraną ścieżkę jako WAV…” wykonuje rzeczywistą ekstrakcję do nowego pliku.
5. Otwórz SRT/ASS, obejrzyj podgląd i użyj „Zapisz kopię napisów…”.
   Zachowywany jest format źródłowy, tekst i czasy. Konwersja ASS↔SRT jest blokowana.

UTF-8 (także BOM) i UTF-16 z BOM są rozpoznawane. Dla starych polskich plików
wybierz CP1250 **przed** otwarciem. Błędne kodowanie nie jest zgadywane.
Efekty ASS są zachowane w kopii, lecz ich renderowania/retimingu nie zweryfikowano;
aplikacja pokazuje ostrzeżenie. Eksport nigdy nie zastępuje istniejącego pliku,
nawet po potwierdzeniu w systemowym dialogu — trzeba podać nową nazwę.

## Testy

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

Testy działają bez modeli i sieci. Integracje wymagają FFmpeg/FFprobe;
przy ich braku są jawnie pomijane. W udokumentowanym uruchomieniu nie było pominięć.
Korpus jest syntetyczny (własne teksty i generowane tony), nie mierzy jakości ASR.
Wyniki i ograniczenia: [docs/validation.md](docs/validation.md).

## Prywatność i status projektu

Aplikacja nie wysyła wideo, napisów ani dialogów do internetu. Nie ma telemetrii.
Logi są domyślnie wyłączone; opcja `--log` włącza wyłącznie komunikaty techniczne
bez treści dialogowych. Instalacja pakietów wymaga internetu; późniejsze operacje
fazy 1 korzystają z lokalnych plików i programów. Modele są planowane na kolejne fazy.

Specyfikacja: [ROADMAP.md](ROADMAP.md), [AGENTS.md](AGENTS.md), [TASKS.md](TASKS.md),
[PROMPTS_BY_PHASE.md](PROMPTS_BY_PHASE.md). Architektura i decyzje:
[docs/architecture.md](docs/architecture.md), [docs/decisions.md](docs/decisions.md).
Historia zmian: [CHANGELOG.md](CHANGELOG.md).
