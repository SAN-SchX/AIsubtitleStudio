# Historia zmian

## 0.1.0 — 2026-10-25

### Faza 0

- Dodano projekt Python 3.12 w układzie src, przypięte zależności i uv.lock.
- Ustalono kontrakty danych, milisekundy/PTS, prywatność i architekturę providerów.
- Dodano własny korpus PL/EN/JA, ASS, generatory zakłóceń i złote czasy.
- Weryfikacja etapu: 20 testów zaliczonych na Linuksie.

### Faza 1

- Dodano polski interfejs PySide6: dialogi, drag/drop, metadane, wybór audio/języka.
- Dodano FFprobe JSON oraz bezpieczne strumieniowe wyodrębnianie PCM WAV.
- Dodano import i eksport kopii SRT/ASS, Unicode/BOM i jawny wybór CP1250.
- Zablokowano nadpisywanie i stratną konwersję ASS/SRT; zachowano style i tagi.
- Dodano diagnostykę zależności i lokalnych modeli Ollama, bez pobierania modeli.
- Dodano testy GUI, procesów, anulowania, PTS, audio i bezpieczeństwa zapisu.
- Przyszłe funkcje AI pozostają jawnie wyłączone. macOS/MLX: niezweryfikowane.
