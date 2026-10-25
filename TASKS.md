# TASKS — kryteria odbioru krok po kroku

> AI: zaznaczaj `[x]` dopiero po wykonaniu i zweryfikowaniu; obok podaj komendę testową lub log. Nie odznaczaj tylko na podstawie obecności funkcji w kodzie.

## Faza 0 — specyfikacja i fixture
- [x] Ustalić ADR o PTS/milisekundach, trybach i pluginach AI.
- [x] Utworzyć `pyproject.toml`, pakiet `src`, testy `pytest`, formatowanie/lint.
- [x] Utworzyć katalog `tests/fixtures` z próbkami własnymi lub legalnie użytymi.
- [x] Syntetyczne generatory SRT do offset +8, -3, skala FPS i punkt cięcia.
- [x] Golden expected timings na prostych testach deterministycznych.


Weryfikacja fazy 0: `.venv/bin/python -m pytest -q` — **20 passed**;
`.venv/bin/ruff check .` — OK. Korpus: 8 SRT + ASS, własne teksty CC0;
bez twierdzenia o rozpoznawaniu mowy. Szczegóły: `docs/validation.md`.

## Faza 1 — działająca aplikacja i media
- [x] Komenda `python -m ai_subtitle_studio` otwiera GUI.
- [x] Drag/drop i dialog wyboru wideo działa.
- [x] ffprobe odczytuje czas, FPS, wszystkie audio tracks.
- [x] Select box audio tracks oraz język źródłowy działają.
- [x] Parser/eksport SRT + ASS z walidacją czasu i Unicode.
- [x] Export bez nadpisywania.
- [x] `scripts/doctor.py` sprawdza programy, model Ollamy i architekturę.
- [x] Co najmniej 10 automatycznych testów jednostkowych.


Weryfikacja fazy 1: pełny `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q`,
testy GUI w `tests/integration/test_gui.py`, media w `tests/integration/test_media.py`,
round-trip i no-overwrite w `tests/unit/test_subtitles.py` i `test_files.py`.
Wyniki końcowe: `docs/validation.md`. GUI zweryfikowano automatycznie offscreen;
**natywna instalacja macOS arm64 i ręczny odbiór na Macu: NOT VERIFIED**.
Nie oznacza to zakończenia całego MVP ani weryfikacji modeli.

## Faza 2 — realna transkrypcja
- [ ] MLX whisper backend działa na realnej lokalnej próbce audio.
- [ ] Obsługa EN, PL, JA wraz z nadpisaniem auto-lang.
- [ ] Chunking i segment time offset nie powodują skoków czasu.
- [ ] Generowanie `.srt` z poprawną numeracją i UTF-8.
- [ ] Gdy model niepobrany, GUI mówi czego potrzeba; brak cichego pobrania.
- [ ] Log informuje o realnym czasie i modelu — bez udawanych metryk.
- [ ] Działa cancel i wątek UI nie jest blokowany.

## Faza 3 — korekta prosta
- [ ] Ręczne shift offset.
- [ ] Automatyczne global shift i różnica tempa, pomiar score.
- [ ] Opcjonalny FFsubsync adapter z obsługą błędów.
- [ ] Unit test +8s i -3s, max error 100ms.
- [ ] Unit test scaling 23.976↔25, max error 100ms.
- [ ] Nie niszczy tekstu cue.

## Faza 4 — semantyczna synchronizacja
- [ ] LLM nie ustawia timestampów bezpośrednio.
- [ ] Matcher monolingual, monotonic DP z lukami i merge/split.
- [ ] Multilingual embeddings przez Ollamę z fallbackiem.
- [ ] Piecewise mapping, breakpoint i anchor confidence.
- [ ] Wartości confidence są opisane jako score heurystyczny, nie skalibrowana szansa.
- [ ] Synthetic +10s mid-episode i utrzymanie poprawnego początku.
- [ ] Test JA speech + PL subtitles na prawdziwych danych i raport błędów.
- [ ] Niepewne kwestie mają jawny status review.

## Faza 5 — tłumaczenie
- [ ] Tłumaczenie batch z glosariuszem, target PL.
- [ ] Structured JSON validation, retry limit, offline fallback.
- [ ] Dokładnie ta sama liczba ID i identyczne timestampy.
- [ ] SRT per language i zabezpieczenie przeciw overwrite.
- [ ] Testy mock: malformed JSON, missing ID, duplicate ID, empty text.

## Faza 6 — edytor
- [ ] Realny player/seek i cue table z dokładnym czasem.
- [ ] Regulacja pojedynczego cue, shift fragmentu, undo/redo.
- [ ] Szukanie niskiego confidence i preview 2–3s naokoło kwestii.
- [ ] Zapis po edycji bez uszkodzenia Unicode ani czasu.

## Faza 7 — obraz, opcja
- [ ] PySceneDetect scene boundaries jako sygnał pomocniczy.
- [ ] OCR znaków na ekranie z ograniczeniem próbkowania.
- [ ] Vision LLM można wyłączyć; brak pełnego skanowania wszystkich klatek.

## Faza 8 — wydanie
- [ ] Cały sezon batch, możliwość przerwania i wznowienia.
- [ ] Eksport Jellyfin `video_basename.pl.srt` z pytaniem przy konflikcie.
- [ ] Aplikacja .app działa na czystym macOS Apple Silicon z dokumentowaną instalacją zależności.
- [ ] Smoke test offline (po instalacji modeli), brak remote calls.
- [ ] Raport wpływu pamięci i użycia dysku na 16 GB RAM.
- [ ] CHECK licencji Qt, FFmpeg, modeli oraz ewentualnego code-signing/notaryzacji.

## Scenariusze katastroficzne (testy regresji)
- [ ] 2 różne źródłowe ścieżki audio: japoński i angielski dub — wybór nie może być przypadkowy.
- [ ] Odcinek zawiera 90s recapu, polskie SRT bez recapu.
- [ ] Czarna klatka lub cisza nie generuje fałszywego dialogu.
- [ ] Po 10 min odcinka przesunięcie zmienia się skokowo o +12s.
- [x] Napisy źródłowe mają nietypową numerację i BOM — `tests/unit/test_subtitles.py::test_bom_and_unusual_indexes`.
- [ ] Anime ASS ma efekty karaoke i style — program ostrzega, jeśli nie umie zagwarantować ich zachowania.
- [ ] Model Ollama jest offline, a transkrypcja musi dalej działać.
- [ ] Użytkownik anuluje podczas FFmpeg i podczas Ollama.
- [ ] Mała ilość pamięci, dysku i brak uprawnień do folderu wyjścia.

## Raport wymagany od AI po każdej fazie

```
Phase: ...
Implemented: ...
Changed files: ...
Test commands and ACTUAL outcomes: ...
Manual macOS checks performed: ...
Not verified / blockers: ...
Known bugs: ...
Next phase: ...
```
