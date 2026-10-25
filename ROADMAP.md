# AI Subtitle Studio — kompletna roadmapa techniczna

**Platforma docelowa:** macOS, Apple Silicon, 16 GB pamięci zunifikowanej; projekt cross-platform tam, gdzie łatwo to zapewnić.
**Język:** Python 3.12; UI w języku polskim (i18n przygotowane na angielski).
**Cel:** prywatne, lokalne przetwarzanie filmów i napisów, bez płatnych API. Pobranie modeli oraz aktualizacji wymaga internetu tylko przy instalacji lub wyraźnej decyzji użytkownika.

## 0. Zakres funkcjonalny

### MVP
- Import filmów `mp4`, `mkv`, `mov`, `avi` (formaty zależą od dostępnych dekoderów FFmpeg).
- Import/eksport tekstowych napisów SRT; podstawowy import/eksport ASS bez usuwania zawartości i stylów.
- Odczyt metadanych przez ffprobe (czas, FPS, wszystkie ścieżki audio, napisy), ręczny wybór ścieżki audio.
- Transkrypcja języka źródłowego modelem Whisper na Apple Silicon, znacznik czasu segmentu, opcjonalne znaczniki słów.
- Wybór języka albo wykrycie automatyczne; możliwość ręcznej korekty.
- Generowanie SRT z rozpoznanego tekstu; zapis jako nowy plik UTF-8.
- Korekta stałego przesunięcia, ograniczona korekta stałego tempa i weryfikacja wyniku.
- Prosty desktop GUI: drag-and-drop, ustawienia, postęp, anuluj, panel z wynikami.
- Żadne nadpisanie oryginalnych napisów bez jawnego potwierdzenia.

### Wersja 1
- Lokalne dopasowanie istniejących napisów do transkrypcji, także przy cięciach filmu i skokach opóźnienia.
- Dopasowanie krzyżowo-językowe japoński↔polski, angielski↔polski, z algorytmem sekwencyjnym i odrzucaniem niepewnych par.
- Tłumaczenie dialogów lokalnym LLM z glosariuszem nazw własnych, walidacją wyniku i zachowaniem czasów.
- Panel ręcznej kontroli, oznaczanie niepewnych kwestii, undo/redo, podgląd wideo.
- Przetwarzanie wsadowe sezonów i eksport zgodny z Jellyfin.

### Wersja 2 — opcjonalnie
- Podstawowa segmentacja obrazu na sceny, OCR napisów ekranowych, opcjonalny niewielki model wizyjny.
- Rozpoznawanie mówców (diarization) po dodatkowej instalacji.
- Trwała historia zadań, ustawienia profili, podgląd waveform i wielościeżkowe napisy.
- Zdalny worker Debian/Jellyfin, gdy architektura klient/serwer zostanie osobno zaprojektowana i zabezpieczona.

## 1. Stos technologiczny

| Komponent | Pierwszy wybór | Cel / uwagi |
|---|---|---|
| Python | 3.12 + venv/uv | Stabilny lokalny backend |
| GUI | PySide6 | Natywne okna i wątki workerów; QMediaPlayer do prostego preview |
| Media | ffmpeg, ffprobe | Lokalny odczyt plików, wybór strumieni, PCM mono 16kHz do ASR |
| Napisy | pysubs2 | SRT, ASS, poprawne czasy i style przy retimingu |
| ASR | mlx-whisper | Akceleracja MLX na Apple Silicon, model large-v3-turbo; średni model fallback |
| Detekcja mowy | silero-vad | Regiony mowy; VAD nie transkrybuje |
| Precyzyjny timing | word_timestamps MLX; opcjonalny aligner z modelami językowymi | Nie uzależniać podstawowej wersji od PyTorch CUDA |
| Prosta synchronizacja | ffsubsync jako opcjonalny adapter + własny fallback | Globalny offset i stała korekta tempa, nie usuwa problemów z montażem |
| Dopasowanie międzyjęzykowe | Ollama + qwen3-embedding:0.6b | Porównanie semantyczne; nie polegać na embedach w izolacji |
| Analiza i tłumaczenie | Ollama + qwen3:4b | Chunking, glosariusz, validowane struktury JSON |
| Baza i cache | SQLite + katalog projektu | Historia, wyniki pośrednie, ponawianie prac |
| Testy | pytest (+ pytest-qt) | Jednostkowe, integracyjne, smoke, testy fixture |
| Packaging | pyside6-deploy (ew. py2app/PyInstaller) | macOS .app; podpisy i notarization to oddzielne działania |

**Ważne:** whisperX na macOS nie powinien być obowiązkową zależnością MVP. Testować oddzielnie backend alignera dla `ja`/`pl` i oferować fallback do czasów z MLX Whisper. W repozytorium WhisperX są domyślne modele alignera dla polskiego i japońskiego, co nie jest gwarancją kompatybilności każdej wersji na macOS.

## 2. Docelowa architektura katalogów

```
ai-subtitle-studio/
├── pyproject.toml
├── README.md
├── AGENTS.md
├── src/ai_subtitle_studio/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── config.py
│   ├── domain/
│   │   ├── models.py               # Cue, TranscriptSegment, AudioTrack, JobResult
│   │   └── errors.py
│   ├── media/
│   │   ├── probe.py                # ffprobe JSON -> modele
│   │   ├── extract.py              # ffmpeg stream selection -> WAV
│   │   └── cache.py
│   ├── subtitles/
│   │   ├── io.py                   # SRT/ASS, kodowania, sanitacja
│   │   ├── quality.py              # normalizacja czasów, CPS i warningi
│   │   └── formats.py
│   ├── speech/
│   │   ├── base.py                 # protokół providerów
│   │   ├── mlx_whisper.py
│   │   ├── vad.py
│   │   └── align.py                # optional forced alignment
│   ├── ai/
│   │   ├── ollama.py              # health/model checks, timeout, retry, JSON
│   │   ├── embeddings.py
│   │   ├── translate.py
│   │   └── prompts.py
│   ├── sync/
│   │   ├── baseline.py            # offset, fps ratio
│   │   ├── matching.py            # candidate scoring
│   │   ├── sequence.py            # monotonic DP + gaps/merges
│   │   ├── warp.py                # offset/drift, breakpoints
│   │   └── confidence.py
│   ├── jobs/
│   │   ├── pipeline.py
│   │   ├── manager.py
│   │   └── state.py
│   ├── storage/
│   │   └── sqlite.py
│   └── gui/
│       ├── app.py
│       ├── main_window.py
│       ├── settings_view.py
│       ├── preview_view.py
│       ├── editor_view.py
│       └── workers.py
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── fixtures/
│   └── golden/
├── scripts/
│   ├── doctor.py
│   └── benchmark.py
└── docs/
    ├── architecture.md
    ├── decisions.md
    ├── install_macos.md
    └── troubleshooting.md
```

## 3. Schemat danych i kontrakty

Na granicach komponentów użyj `pydantic` albo typowanych dataclass, lecz nie mieszaj obu bez powodu.

```
MediaInfo(duration_ms, fps_num, fps_den, audio_tracks[], subtitle_tracks[])
AudioTrack(stream_index, language?, channels?, codec?, title?)
TranscriptSegment(id, start_ms, end_ms, language, text, words[], confidence?, source='asr')
SubtitleCue(id, start_ms, end_ms, text, style?, original_start_ms?, original_end_ms?)
AlignmentPair(subtitle_ids[], transcript_ids[], confidence, reason, status)
JobConfig(video_path, subtitle_path?, mode, audio_stream_index?, source_language?, target_language?, quality_preset, model_id?, output_dir?)
JobResult(output_paths[], warnings[], summary, low_confidence_cue_ids[], metrics)
```

Inwarianty: czas w **milisekundach jako liczba całkowita** w całej logice domenowej; 0 <= start < end; brak ujemnych czasów; rozróżnianie `unknown` i wartości zerowych; ustalenie jednej konwencji offsetu dla wszystkich przebiegów. Wykrywać i raportować niewspierane formaty/ścieżki zamiast cichego pomijania.

## 4. Główne pipeline'y

### A. Generowanie napisów bez istniejącego pliku

1. ffprobe: odczyt czasu, FPS, ścieżek i języków.
2. Użytkownik wybiera strumień audio; ffmpeg tworzy WAV mono PCM 16k, bez zmiany synchronizacji.
3. VAD wykrywa regiony mowy, opcjonalne przycinanie materiału.
4. MLX Whisper transkrybuje w wybranym lub wykrytym języku; podział dłuższych plików na krótsze odcinki z overlapem i korektą offsetów.
5. Opcjonalnie doprecyzowanie czasów słów; tam, gdzie aligner jest niedostępny, zachowaj czasy segmentów.
6. Segmentator tworzy linie napisów ze zrozumiałymi granicami zdań, długością i CPS; nie przepisuje znaczenia.
7. Lokalny walidator odrzuca puste, ujemne, niechronologiczne i nieprawidłowe cue; oznacza ostrzeżenia, nie ukrywa ich.
8. Zapis `.ja.srt`, `.en.srt` lub `.pl.srt` i raport jakości.

### B. Tłumaczenie

1. Odczyt już zsynchronizowanych cue i ich identyfikatorów.
2. Partie 10–30 kwestii z kontekstem sąsiednich wypowiedzi, glosariusz nazw własnych, język docelowy.
3. Ollama `POST /api/chat`, `format` ustawiony na JSON Schema, Pydantic waliduje wynik.
4. Rezultat **dokładnie z listą ID**; brak możliwości tworzenia lub usuwania cue bez zgody.
5. Nie ufać wygenerowanym przez LLM znacznikom czasu; czasy pochodzą z oryginalnych wypowiedzi.
6. Kontrola ilości cue, niepustych tekstów, powtórzeń, jakości i długości wierszy; w razie błędu ponowić ograniczoną liczbę razy i zgłosić do ręcznej korekty.
7. Zapisać jako nowy plik UTF-8 z właściwym sufiksem języka, nie zmieniając oryginału.

### C. Inteligentna synchronizacja istniejących napisów

Wejścia: wideo, oryginalna ścieżka audio, źle zsynchronizowany plik SRT lub ASS.

**Krok 1: Baseline.** Spróbuj przesunięcia globalnego i liniowej korekty tempa: `t_new = a*t_old + b`. Oceniaj wynik miarą pokrywania się aktywności mowy z napisami oraz liczbą dopasowań tekstowych; nie przyjmuj automatycznie baseline, jeśli niski confidence.

**Krok 2: Transkrypcja.** ASR wypowiada dialogi z ich czasami na osi wideo. Lokalny preprocessor normalizuje tekst bez usuwania ważnych nazw. Używaj oryginalnego audio (japońskiego dla anime), nie tłumacz na tym etapie na siłę.

**Krok 3: Wybór strategii.**
- Ten sam język: podobieństwo normalizowanych fraz (tokenowe i n-gramowe), warianty transkrypcji, dopasowanie wielu cue do jednej wypowiedzi.
- Różne języki: porównanie embeddingów wielojęzycznych, opcjonalne tłumaczenie pomocnicze ograniczonego fragmentu; dodać score chronologii i długości.
- Sceny i cisze są wskazówkami, ale **nie dowodem** na odpowiedni dialog.

**Krok 4: Dopasowanie sekwencji.** Buduj kandydatów w oknie czasowym; wykorzystaj monotoniczne DP/DTW, przewidujące pominięcia i łączenia 1:2 / 2:1. Funkcja kosztu uwzględnia podobieństwo semantyczne, porządek, lokalne odchylenie czasowe, spójność i karę za zbyt duży skok. Wykorzystaj kilka niezależnych silnych anchorów. Nie dopasowuj każdej kwestii z przymusu.

**Krok 5: Wyznaczenie zmian montażu.** Z dopasowanych anchorów estymuj odcinkami funkcję `t_video = f(t_sub)`: stałe przesunięcia na odcinkach, lokalny drift oraz punktowe skoki. Odcinki tną się przy statystycznych discontinuity; ogranicz szalejącą interpolację, nie ekstrapoluj przez duże niepewne przerwy.

**Krok 6: Aktualizacja czasów.** Dla wysokiej pewności użyj granic ASR/VAD, dla umiarkowanej przeliczonego przedziału z f(t). Zachowuj kolejność, logiczne przerwy i format; nie przepisuj tekstu ani stylów bez wyraźnego trybu.

**Krok 7: Wynik.** Zwróć per-cue: oryginalny czas, poprawiony czas, delta, pewność, anchor, ostrzeżenia i status do kontroli. Niepewne cue pozostaw do ręcznej weryfikacji zamiast cicho wstawiać losowe czasy.

**Szczególnie dla japoński→polski:** krzyżowo-językowe semantyczne podobieństwo może mylić krótkie wypowiedzi („Tak”, „Nie”, okrzyki), parafrazy, wypowiedzi wielogłosowe i onomatopeje. Próg i wagę dopasowań trzeba skalibrować na rzeczywistych materiałach. Nie obiecywać 100% dokładności.

## 5. Zasady synchronizacji i jakości

- Domyślne zasady napisów powinny być konfigurowalne: do 2 linii, zwykle do ~42 znaków w linii alfabetu łacińskiego, orientacyjnie 17–21 znaków/sekundę. Dla języków CJK nie stosuj ślepo tych samych granic.
- Preferuj granice zdań, krótkie pauzy, nie przecinaj słów, uwzględniaj shot-change jako pomocniczy sygnał.
- Nie dopuszczaj do negatywnych czasów, zerowego czasu wyświetlania, dublowanych cue, niezrozumiałego łamania linii.
- Nakładające się kwestie i karaoke ASS to osobne świadome przypadki — nie niszcz animacji i tags; przy braku wsparcia pokaż ostrzeżenie.
- Wewnątrz silnika nie używaj klatek FPS jako podstawowej miary czasu: korzystaj z milisekund oraz PTS z ffprobe; FPS uwzględniaj przy konwersji historycznych napisów.
- Wykorzystuj bezpieczne nazwy plików i unikalne ścieżki wyjścia, bez nadpisywania wejścia.
- Przed zapisem waliduj czy input i output są różnymi plikami (także przez symlinki).

## 6. UI/UX — ekrany

1. **Start** — wybór pliku (drag-and-drop), metadane wideo, język, audio track.
2. **Tryby** — Synchronizuj / Generuj / Generuj i tłumacz / Tylko tłumacz.
3. **Model i wydajność** — szybki / zbalansowany / dokładny; status lokalnej Ollamy, pamięci, modeli.
4. **Kolejka zadań** — postęp per stage, ETA tylko gdy wiarygodne, anuluj/wznów, logi.
5. **Edytor** — odtwarzacz, lista cue, czas wejścia/wyjścia, tekst, confidence, przycisk odsłuchu.
6. **Raport** — lista niepewnych cue, wykres delta w czasie, jakość, eksport.
7. **Eksport** — SRT / ASS, kod języka, wybór folderu i tryb Jellyfin.

Interfejs nie może się zawieszać: praca obliczeniowa poza wątkiem UI (QThread / worker), sterowana sygnałami; anulowanie ma zakończyć procesy FFmpeg i zwolnić model.

## 7. Ograniczenia Maca 16 GB RAM

- Uruchamiać modele kolejno: ASR, następnie embeddings/LLM; jeden ciężki job naraz domyślnie.
- Preferować 4B quantized zamiast 8B przy jednoczesnej pracy z GUI i Whisperem.
- Ograniczyć `num_ctx`, rozsądnie zarządzać `keep_alive` Ollamy, sprawdzać pamięć i obsługiwać awarie out-of-memory.
- Wyniki pośrednie (WAV/transcript/embeddingi) cachować po fingerprint pliku + wybranej ścieżki + wersji modelu.
- Nie zakładać, że 90 minut materiału zawsze zmieści się w RAM. Obrabiać porcjami, zamykać pliki, usuwać zasoby tymczasowe po potwierdzeniu zapisu.
- Użytkownik musi móc w ustawieniach wyłączyć ciężki wariant modelu.

## 8. Szczegółowy plan wdrożenia

### Faza 0: Projekt i testowy korpus
- Zapisać ADR dot. stanu MVP, architektury providerów i schematu danych.
- Przygotować 5–10 krótkich, legalnie udostępnianych fixture AV/SRT w różnym języku.
- Generować syntetyczne przesunięcia SRT: +8 s, -3 s, skalowanie 23.976↔25, lokalny skok +10 s po 2 min., brak kilku cue, powtórzony dialog.
- Zapisać wzorce oczekiwanych wyników (golden files) i scenariusze awarii.

### Faza 1: Szkielet, media i SRT
- `pyproject.toml` z zależnościami minimalnymi; instalacja arm64; logowanie, `doctor` zależności.
- Testy importów, sanitacji, parsera, exportu, no-overwrite; ffprobe/ffmpeg.
- Start GUI, drag-and-drop, odczyt listy audio tracks, wybór języka.

### Faza 2: Transkrypcja na Macu
- Adapter MLX Whisper z kontrolą wersji i przyjaznym komunikatem o braku modelu.
- WAV 16k + transkrypcja fragmentami + stitching bez dubli na granicach.
- Sprawdzenie `ja`, `en`, `pl` na krótkich plikach.
- SRT z rzeczywistych wypowiedzi; bez LLM i bez internetu po pobraniu modeli.

### Faza 3: Proste retiming
- Ręczny offset, FPS scale i FFsubsync jako opcja, nie bezwzględna zależność.
- Ocena jakości i fallback do „nie udało się zsynchronizować”, jeśli wynik nie jest wiarygodny.
- Testy przed/po na syntetycznych fixture.

### Faza 4: Dopasowanie transkrypcji
- Matcher tego samego języka, confidence, monotonic DP, obsługa luk.
- Dopasowanie międzyjęzykowe: qwen3-embedding:0.6b + ograniczone tłumaczenie kontekstowe przez qwen3:4b.
- Piecewise mapping, wykrywanie breakpointów i odcinków o zmiennym opóźnieniu.
- Przegląd raportu i poprawa błędów na golden fixtures.

### Faza 5: Tłumaczenia
- Ollama health-check i JSON-schema outputs.
- Tłumaczenie partii z kontekstem, nazwami postaci i czarną listą halucynacji.
- Weryfikacja liczby ID i całej sekwencji, formater tekstu i kontrola czasu.

### Faza 6: Edytor i kontrola
- Wideo preview, cue table, narzędzia shift/split/merge/undo/redo, confidence heatmap.
- Odtwarzanie 2–3 s przed i po wybranej kwestii; użyj komponentu preview bez blokowania UI.

### Faza 7: Dodatkowa wizja
- PySceneDetect wykrywa cięcia; OCR czyta tekst tylko w wybranych klatkach/ROI.
- Vision LLM opcjonalny i niskoczęstotliwościowy; na 16 GB nie analizować każdej klatki full-res.
- Każda hipoteza wynikająca tylko z obrazu wymaga walidacji albo oznaczenia jako niepewna.

### Faza 8: Wdrożenie
- Przygotować .app i instalator, instrukcję instalacji FFmpeg / Ollama / modeli.
- Test świeżej maszyny i całkowitej pracy offline po instalacji.
- Obsługa całych sezonów, export `.pl.srt` pasujący do Jellyfin, bez nadpisania.
- Dokumentacja bezpieczeństwa, licencji i plan ewentualnego podpisania/notaryzacji macOS.

## 9. Testowanie

**Testy jednostkowe**: parser SRT/ASS, zachowanie `id`, poprawność timecode, ffprobe JSON parsing, wyjściowe nazwy, unicode japoński/polski, brak cichego nadpisania, brak zależności od sieci.

**Integracyjne (z modelami jako opcjonalne)**: fałszywy provider ASR zwraca ustalone dialogi; faktyczny MLX Whisper transkrybuje lokalną próbką; Ollama mock emuluje sukces/pustą odpowiedź/błędny JSON/timeout; pipeline wznawia się z checkpointu.

**Golden tests**: porównanie do ręcznych napisów referencyjnych za pomocą mediany błędu czasu początku/końca oraz odsetka trafionych cue w tolerancji 0.5 s i 1 s. Zgłaszaj osobno wskaźniki dla `pl→pl`, `en→pl`, `ja→pl` oraz skoków montażowych. Nie zakładaj odgórnie jednego poziomu jakości.

**Stabilność**: 5 minut ciszy, wideo bez audio, 2 ścieżki audio, niestandardowe napisy ASS, obraz tylko z napisami, uszkodzony MKV, niepoprawny encoding, długie ścieżki z polskimi znakami, zatrzymanie procesu, brak Ollamy, mało wolnego miejsca, pamięć.

**Bezpieczeństwo/prywatność**: brak wysyłania filmów/napisów do sieci, brak niejawnej telemetrii, tylko loopback `127.0.0.1:11434` dla Ollamy domyślnie, brak shell=True na ścieżkach pochodzących od użytkownika, rejestrowanie wyłącznie metadanych bez pełnych dialogów w logach domyślnych.

## 10. Cele akceptacyjne (nie gwarantowane wyniki modeli)

- Jedna komenda uruchamia GUI z instrukcji lokalnej.
- `doctor` jasno raportuje brak wymaganych komponentów i nie pobiera automatycznie ogromnych modeli bez zgody.
- Pipeline transkrypcji kończy się poprawnym SRT z prawdziwymi tekstami i czasami.
- Test syntetyczny +8 s i -3 s przywraca oczekiwane cue z tolerancją ±100 ms (bez modelu AI).
- Test liniowego scalingu potwierdza wyliczenie czasów względem reference.
- Test ze skokiem montażowym (+10 s po punkcie cięcia) wymaga rozpoznania co najmniej dwóch odcinków; kryterium błędu dla rzeczywistego audio ustalić po pomiarach.
- Tekst oryginalnego SRT w trybie „synchronizuj” pozostaje niezmieniony co do treści.
- Anulowanie nie zostawia procesu FFmpeg w tle; wejściowe pliki pozostają niezmienione.
- Generacja polskiego tłumaczenia zachowuje dokładnie ID i timecode, błędne odpowiedzi LLM nie są zapisywane cicho.
- Aplikacja działa lokalnie po zainstalowaniu zależności i wcześniej pobranych modeli.

## 11. Utrzymanie i ryzyka

- ASR może halucynować podczas ciszy, muzyki i krzyków. Wymagany VAD i confidence.
- LLMy tłumaczą sens, nie odmierzają dźwięku; czas pochodzi z ASR/algorytmu.
- Tłumaczenia anime mogą nie mieć dosłownego odpowiednika dialogów, szczególnie honorifics i gry słów.
- Zewnętrzne SRT często pochodzi z innego wydania filmu lub innego montażu.
- Całkowita zgodność ASS karaoke/stylów wymaga testów; nie obiecywać bezstratności bez weryfikacji.
- Integracja modeli HF/torch może zależeć od pakietów i macOS; adapter, opcjonalne extra i fallback są obowiązkowe.
- Obowiązki licencyjne FFmpeg/Qt/modeli sprawdzić osobno przed dystrybucją produktu.
- Ocena opóźnień musi mieć raport niepewności. „95% confidence” nie oznacza „95% poprawności” bez kalibracji.

## 12. Polecenia startowe na Macu

Weryfikacja środowiska w Terminalu:

```bash
uname -m
python3 --version
ffmpeg -version
ffprobe -version
ollama --version
```

Opcjonalna instalacja brakującego FFmpeg przez Homebrew:

```bash
brew install ffmpeg
```

Pobranie lokalnych modeli Ollama:

```bash
ollama pull qwen3:4b
ollama pull qwen3-embedding:0.6b
ollama list
```

Modele Whisper są pobierane oddzielnie przy użyciu zgodnego adaptera MLX; szczegóły jego komend mają zostać potwierdzone przez implementującego agenta z aktualną dokumentacją. `brew` nie jest jedyną metodą instalacji FFmpeg. Nie zakładać, że `ollama serve` trzeba uruchamiać, jeżeli desktop Ollama już nasłuchuje.

## 13. Export Jellyfin

Dla pliku `Death Note S01E01.mkv` zapisuj `Death Note S01E01.pl.srt` po potwierdzeniu użytkownika i sprawdzeniu konfliktu. Jeśli taki plik istnieje, domyślnie wybrać inną nazwę zawierającą kod języka albo poprosić o decyzję. Zachować UTF-8, numerację cue i sortowanie. Jellyfin rozpoznaje zewnętrzne napisy po sufiksach nazw odpowiadających plikowi odcinka.

## 14. Kiedy projekt jest rzeczywiście gotowy

Nie wtedy, gdy istnieje ładny GUI albo zrzuty ekranu. Gotowy jest wtedy, gdy agent potrafi pokazać: kod, instrukcję instalacji, prawdziwy log testów, wideo testowe z wygenerowanym SRT, poprawione SRT po sztucznym przesunięciu, demonstrację lokalnego modelu i raport z ograniczeniami na autentycznych klipach w 3 językach.
