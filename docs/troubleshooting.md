# Rozwiązywanie problemów

- **Brak FFmpeg/FFprobe:** uruchom `python scripts/doctor.py`; doinstaluj oba
  programy (na Macu np. `brew install ffmpeg`) i sprawdź PATH. Aplikacja nie
  instaluje systemowych programów samoczynnie.
- **Brak Ollamy / qwen3:** ostrzeżenie jest oczekiwane w fazie 1 i nie blokuje
  importu ani eksportu. Nie ma jeszcze transkrypcji ani tłumaczenia.
- **Niepoprawne kodowanie SRT:** wybierz CP1250 lub UTF-16 przed importem.
  Aplikacja nie zastępuje uszkodzonych znaków znakami zapytania.
- **Odmowa zapisu:** wybierz nową nazwę w zapisywalnym folderze. Istniejący plik,
  link lub plik utworzony przez inny program w trakcie eksportu nie jest zastępowany.
  Publikacja wymaga obsługi hardlink na danym systemie plików; brak takiej obsługi
  jest jawnym błędem, bez niebezpiecznego fallbacku.
- **Błędny film:** obsługiwane są lokalne MP4/MKV/MOV/AVI. Adresy URL, playlisty
  sieciowe i niekompletne/uszkodzone pliki są odrzucane. FFmpeg dopuszcza tylko
  protokoły file/pipe; dane nie trafiają do zdalnych dekoderów.
- **Duży film:** ekstrakcja działa strumieniowo na dysk; potrzebna jest przestrzeń
  na PCM (około 115 MB/godz. przy 16 kHz mono 16 bit). Bieżący limit operacji
  multimedialnej to 60 s; dłuższa ekstrakcja zgłosi błąd i nie opublikuje części WAV.
  Automatyczny podział długich filmów to faza 2.
- **ASS:** standardowe kolumny Events są obsługiwane; niestandardowy układ jest
  odrzucany zamiast interpretowania błędnych czasów. Kopia zachowuje sekcje źródła.
  Karaoke/animacja/rysunki mogą wymagać osobnego renderera i przyszłych testów.
- **Chmura bez ekranu:** ustaw `QT_QPA_PLATFORM=offscreen` wyłącznie do testów.
  Komunikaty Qt o `propagateSizeHints()` w tym trybie nie oznaczają błędu testu.
