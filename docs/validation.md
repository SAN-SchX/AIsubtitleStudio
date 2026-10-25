# Rzeczywiste wyniki weryfikacji

## Faza 0 — 2026-10-25

Środowisko: Linux x86_64, Python 3.12.14. Instalacja `uv sync --python 3.12`
zakończona powodzeniem; wersje zapisano w `uv.lock`.

- `.venv/bin/python scripts/generate_fixtures.py` — wygenerowano 8 SRT + 1 ASS.
- `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` — **20 passed in 0.26s**.
- `.venv/bin/ruff check .` — OK; `.venv/bin/ruff format .` — wykonano.

Testy sprawdzają walidację modeli, Unicode, deterministyczną reprodukcję korpusu,
niezależne złote czasy +8 s / -3 s / skalowania / skoku po 120 s oraz luki
i powtórzenia. Nie testują odzyskiwania przesunięcia: to fazy 3–4.

Niezweryfikowane: macOS arm64, modele, ASR i rzeczywiste nagrania mowy.

## Faza 1 — 2026-10-25

Środowisko: Linux x86_64, Python 3.12.14, Qt/PySide6 6.10.1,
FFmpeg/FFprobe 7.1.5. **Nie wykonano ręcznych testów macOS.**

| Polecenie (z katalogu repozytorium) | Rzeczywisty wynik |
|---|---|
| `UV_CACHE_DIR=/workspace/.cache/uv uv sync --frozen` | OK, 18 pakietów, ponowne wykonanie bez zmian lockfile |
| `QT_QPA_PLATFORM=offscreen .venv/bin/python -m pytest -q` | **81 passed in 4.81s**, 0 failed, 0 skipped |
| `.venv/bin/ruff check .` | All checks passed |
| `.venv/bin/ruff format --check .` | 31 files already formatted |
| `QT_QPA_PLATFORM=offscreen .venv/bin/python -m ai_subtitle_studio --smoke-test` | Kod wyjścia 0; rzeczywiste okno Qt otwarto i zamknięto offscreen |
| `.venv/bin/python scripts/doctor.py` | Kod 0; wymagane zależności OK; ostrzeżenia: Linux zamiast macOS arm64, lokalna Ollama niedostępna |
| `.venv/bin/ai-subtitle-studio doctor --no-ollama` | Kod 0, sprawdzenie Ollamy jawnie pominięte |
| `UV_CACHE_DIR=/workspace/.cache/uv uv build` | Zbudowano wheel i sdist 0.1.0 w `dist/` (ignorowane przez Git) |
| `git diff --check` | OK |

### Co faktycznie sprawdzono

- Odczyt prawdziwych, generowanych lokalnie plików MP4/MKV, 25 FPS,
  metadanych PL/JA/EN, absolutnych indeksów ścieżek oraz czasu PTS.
- Wybór audio: oddzielne tony 440/880 Hz zmierzono w zapisanych WAV,
  nie tylko sprawdzono argument `-map`. Format PCM 16 bit, mono, 16000 Hz.
- Start kontenera 3000 ms i audio 3250 ms: WAV zachowuje 250 ms ciszy,
  co zmierzono na próbkach dźwięku.
- Brak audio, uszkodzony plik, niewłaściwy strumień, timeout, brak narzędzia.
- Anulowanie działającego **rzeczywistego FFmpeg**: proces zakończony/reaped,
  brak częściowego WAV i pliku tymczasowego. Osobno 3 powtórzenia anulowania
  działającego procesu potomnego oraz 3 wywołania już anulowanej ekstrakcji.
- GUI: system zdarzeń Qt drag/drop wideo i SRT, dialog wyboru, audio/język,
  eksport kopii, odmowa nadpisania, naprawa po błędnym imporcie, cancel i close.
- SRT: Unicode PL/JA, długie linie, BOM UTF-8/UTF-16, nietypowe indeksy,
  CP1250 za jawnym wyborem, błędne czasy/znaki/encoding, limit rozmiaru.
- ASS: style, tagi karaoke, aktor, komentarze i dodatkowe sekcje pozostają
  w kopii. Nieobsługiwane kolumny i niepoprawne zdarzenia są odrzucane.
- Zapis: oryginał, symlink, hardlink, wiszący symlink i wyścig z innym zapisem
  są chronione przed zastąpieniem; sprzątanie po niepowodzeniu.
- Doctor: stały loopback, modele, błędny JSON, nadmierna odpowiedź, brak usługi,
  timeout i odrzucenie przekierowania. To testy adaptera diagnostycznego,
  **nie testy generowania przez LLM**.

Testy Pythona blokują połączenia sieciowe. FFmpeg dostaje tylko protokoły file/pipe.
Nie pobierano modeli, filmów ani transkrypcji. Fixture AV to kolor i tony,
nie nagrana mowa i nie pomiar jakości rozpoznawania języków.

### Wykryte i naprawione podczas prac

1. Pierwszy pełny test SRT: 1 failed, 55 passed. Biblioteka usuwała niektóre
   tagi HTML i literały podczas przejścia przez ASS. Import przechowuje teraz
   oryginalny tekst SRT, a eksporter nie wykonuje tej stratnej konwersji.
2. Pierwsze testy GUI kończyły się błędem natywnym przy obsłudze kolejki zdarzeń
   po utracie referencji do okna przez helper testowy. Fixture przechowuje silną
   referencję do końca testu i jawnie zamyka okno przed usunięciem. Nie wyłączono
   testów ani asercji; siedem scenariuszy GUI przechodzi w pełnym zestawie.

### Granice weryfikacji

- **NOT VERIFIED:** instalacja i ręczny GUI na MacBooku Air M5 / macOS arm64,
  natywne dialogi Findera, dostępność, wydajność i zużycie 16 GB pamięci.
- **NIEZAIMPLEMENTOWANE:** fazy 2–8, w tym MLX/Whisper, VAD, synchronizacja,
  tłumaczenie, edytor, odtwarzacz, batch, `.app` i notaryzacja.
- Nie oceniano rzeczywistego anime ASS, mowy PL/EN/JA ani działania pobranych modeli.
  Ostrzeżenia o efektach ASS nie stanowią gwarancji renderowania ani retimingu.
- Ekstrakcja jest strumieniowa, ale ma limit 60 s działania narzędzia; dzielenie
  pełnych filmów do ASR nie należy do tej fazy. Napisy: do 16 MiB, podgląd 500 wierszy.
- Brak wykrytych, nierozwiązanych błędów w zakresie wykonanych testów;
  to nie deklaracja gotowości całej docelowej aplikacji.

### Zapis konfiguracji środowiska

Zapisano w szkicu `install_script` (zamrożona instalacja i doctor) oraz `start_skill`
(katalog pracy, komendy GUI/testów, prywatność i granice faz). Nie zmieniano sieci,
sekretów ani listy repozytoriów. Zapis szkicu nie publikuje środowiska. Aby utrwalić
wersję do kolejnych zadań, należy przejrzeć i zapisać zmiany w ustawieniach środowiska,
a następnie je opublikować. Nie zweryfikowano odtworzenia w nowym zadaniu.

Pełny wykaz plików: [files.md](files.md). Dalszy etap to faza 2, wyłącznie
po osobnym zleceniu użytkownika.
