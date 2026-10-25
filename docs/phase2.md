# Faza 2 — lokalna transkrypcja MLX

**Status:** implementacja i przenośne testy gotowe; odbiór rzeczywistego ASR na
macOS arm64 **NOT VERIFIED**. Nie rozpoczęto fazy 3. Nie ma synchronizacji ani LLM.

## Uruchomienie na Macu

W istniejącym checkout, z Pythonem 3.12 arm64 i FFmpeg/FFprobe:

```bash
uv sync --frozen --extra speech
```

Przypięto `mlx-whisper==0.4.3`, `mlx==0.32.4`, `huggingface-hub==0.36.0`;
zależności `speech` są instalowane tylko na macOS arm64. Pełne wersje przechodnie
są w `uv.lock`. Koła MLX 0.32.4 i Torch 2.14.1 z lockfile wymagają macOS 14 lub nowszego; zgodność zestawu z M5
wymaga wykonania testów na docelowym systemie. Instalacja w Linuksie z `--extra speech`
celowo pomija MLX i nie stanowi weryfikacji jego instalacji na Macu.

Wybierz istniejący lokalny model w GUI albo pobierz go **świadomie**:

```bash
uv run --frozen --extra speech python -m ai_subtitle_studio download-model \
  --preset speed --accept-download
```

Wariant `speed`: `mlx-community/whisper-small-mlx`, wariant `accurate`:
`mlx-community/whisper-large-v3-turbo`. Domyślny katalog to
`~/Library/Application Support/AI Subtitle Studio/models/<nazwa-modelu>`.
Możesz podać `--model-dir /nowy/katalog`. Potrzebne są `config.json` i
`weights.safetensors` lub `weights.npz`, zgodnie z loaderem wersji 0.4.3.
Sama obecność plików jest kontrolą struktury, nie dowodem poprawności wag.

Pobieranie nie wysyła danych użytkownika. Nie pobiera skryptów z repozytorium
modelu i nie wykonuje kodu z Hugging Face. Nie nadpisuje istniejącego modelu ani
innych plików. Gdy pobranie się nie powiedzie, niekompletny katalog nie jest
używany do ASR; wybierz nowy katalog przy ponowieniu. Nie wyłączaj TLS.

W tym środowisku `huggingface.co` odpowiada odmową proxy **403 Forbidden**.
Nie potwierdzono zdalnej dostępności ani pobrania tych presetów. Do świadomego
pobierania w chmurze mogą być potrzebne dodatki w ustawieniach sieci:
`huggingface.co` oraz host transferowy wskazany przez odpowiedź Hugging Face
(np. `cas-bridge.xethub.hf.co`). Nie zmieniono allowlisty i nie pobrano wag.
Na własnym Macu polityka sieci może być inna.

Kontrola i GUI:

```bash
uv run --frozen --extra speech python -m ai_subtitle_studio doctor \
  --no-ollama --check-speech --model-dir "/pełna/ścieżka/do/modelu"
uv run --frozen --extra speech python -m ai_subtitle_studio
```

Wybierz wideo, konkretną ścieżkę audio, język i lokalny model. „Transkrybuj do
nowego SRT…” wymaga nowej nazwy pliku. Dla auto-języka proponowana nazwa to
`.transkrypcja.srt`; aplikacja nie zgaduje sufiksu `.pl` przed wykryciem języka.

CLI (indeks `--audio-stream` pochodzi z FFprobe i nie jest numerem z listy języków):

```bash
uv run --frozen --extra speech python -m ai_subtitle_studio transcribe \
  --video "/filmy/Odcinek.mkv" --audio-stream 1 --language ja \
  --model-dir "/pełna/ścieżka/do/modelu" --output "/napisy/Odcinek.ja.srt" --log
```

Języki w CLI: `auto`, `pl`, `en`, `ja`. Anulowanie: przycisk GUI albo Ctrl+C w CLI.
Nie trzeba uruchamiać Ollamy; etap ASR nie używa żadnego LLM.

## Jak działa pipeline

1. Waliduje nowy plik wyjściowy, media, audio i miejsce na dysku.
2. FFmpeg zapisuje PCM 16 kHz mono do prywatnego katalogu tymczasowego z zachowaniem
   opóźnienia audio. Ekstrakcja dla ASR ma limit 3600 s; ręczny eksport WAV nadal 60 s.
3. WAV pozostaje na dysku (około 115 MB/h). W pamięci jest jedno okno do 30 s,
   zwykle rdzeń 25 s plus po 1 s kontekstu. Brak wielogodzinnej tablicy audio w RAM.
4. Bramka amplitudy pomija ciszę. Model dostaje `task=transcribe`, czasy słów,
   `verbose=None`, bez kontekstu tekstowego poprzedniego okna. Pierwszy niepusty
   wynik ustala auto-język dla całego zadania.
5. Jeden proces MLX utrzymuje jeden model między oknami. Słowa otrzymują offset
   okna. Rdzenie mają rozłączne przedziały własności; tekst i nakładające się czasy
   służą do odrzucania powtórzenia tego samego słowa na styku. Rozłączne czasowo
   powtórzenia typu „Tak. Tak.” pozostają. Brak czasów słów jest ostrzeżeniem,
   nie pretekstem do wymyślania czasów wewnątrz segmentu.
6. Segmentacja korzysta z czasów słów, długości i przerw. Długie/niepewne kwestie
   są oznaczane do kontroli. CPS i confidence są heurystykami, nie skalibrowaną
   miarą prawdopodobieństwa poprawności. Nie ma edytora w tej fazie.
7. Publikuje SRT atomowo bez zastępowania plików. Cancel/błąd przed publikacją
   sprząta WAV i kończy proces potomny. Model jest zwalniany przez zakończenie procesu.

Postęp pokazuje rzeczywistą liczbę zakończonych okien; ekstrakcja ma wskaźnik
nieokreślony zamiast zmyślonego procentu. Logi zawierają model/katalog modelu,
zmierzony czas i liczbę okien, bez tekstu dialogów.

## Co sprawdzono tutaj

Linux x86_64, Python 3.12.14, FFmpeg 7.1.5, Qt offscreen.
Pełny zestaw: **140 passed, 3 skipped in 5.94s**; trzy pominięcia to realny MLX.
Dokładne komendy i wyniki: [validation.md](validation.md). Sprawdzono:

- rzeczywista ekstrakcja PCM i zapis SRT z kontrolowanym providerem dla PL/EN/JA;
- bezwzględne czasy, kontekst, usuwanie duplikatu z jitterem i zachowanie powtórzeń;
- auto-język, ręczny wybór, segmentacja, walidacja błędnych danych i brak pustego wyniku;
- odmowa nadpisania, cancel, brak miejsca, zamykanie providera w `finally`;
- prawdziwy proces transportowy do testów (bez MLX): reuse, offline flags,
  timeout, błędna odpowiedź, błąd pamięci i reaping po anulowaniu;
- GUI: poprawne blokowanie ASR, sygnały postępu, rzeczywiste zdarzenia okna
  podczas oczekiwania, zapis i anulowanie z testowym providerem;
- zgoda na download sprawdzona przed kontaktem z siecią; testy pobierania są mockowane.

Nie jest to dowód działania modelu na mowie. Nie wykonano testów M5/Metal,
zużycia 16 GB RAM, jakości segmentacji, VAD ani rzeczywistych wag modelu.

Sprawdzono API przypiętego pakietu 0.4.3: koło z PyPI zweryfikowano względem
SHA-256 opublikowanego w metadanych PyPI. Odczytano `load_models.py`, `transcribe.py`
i `tokenizer.py`: lokalny katalog jest obsługiwany, tokenizer ma zasoby w pakiecie.
Nie założono, że nowszy kod z gałęzi `main` jest identyczny z wydaniem.
Źródło wydania: https://pypi.org/project/mlx-whisper/0.4.3/.

## Prawdziwy odbiór PL/EN/JA — do wykonania na Macu

Przygotuj własne/legalne krótkie WAV PCM mono 16 kHz (do 30 s), każde zawierające
rzeczywistą mowę w danym języku. Manifest JSON obok plików:

```json
{
  "pl": {"wav": "pl.wav", "expected_phrase": "naprawdę wypowiedziana fraza"},
  "en": {"wav": "en.wav", "expected_phrase": "phrase actually spoken"},
  "ja": {"wav": "ja.wav", "expected_phrase": "実際の発話"}
}
```

```bash
AISUBTITLE_ASR_CORPUS="/korpus/manifest.json" \
AISUBTITLE_MLX_MODEL_DIR="/modele/whisper-small-mlx" \
uv run --frozen --extra speech pytest -q tests/integration/test_mlx_native.py
```

Wykonaj również transkrypcję filmu przez GUI, sprawdź czasy SRT na odsłuchu,
anulowanie i brak osieroconego procesu. Powtórz z presetem dokładnym. Dopiero
po tych sprawdzeniach można odhaczyć realny backend i obsługę mowy w TASKS.md.

**Znane ograniczenia:** filtr amplitudy nie jest Silero VAD; nie odróżnia muzyki
od mowy. Brak automatycznej walidacji halucynacji na prawdziwej ciszy/muzyce.
Dedupikacja, formatowanie CJK, auto-język dla filmu mieszanego oraz czasy bez
word timestamps wymagają oceny na realnym materiale. Nie obiecujemy konkretnej
jakości rozpoznawania ani bezbłędnego łączenia każdego dialogu.
