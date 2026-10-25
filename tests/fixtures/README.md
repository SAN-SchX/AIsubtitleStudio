# Korpus syntetyczny

Teksty PL/EN/JA i style ASS napisano na potrzeby projektu. Są udostępnione jako
CC0-1.0 (public domain dedication). To dane testowe, nie dialogi z filmu.
`python scripts/generate_fixtures.py` odtwarza osiem SRT i jeden ASS.
PL zawiera powtórzone „Tak.” i przerwę obejmującą punkt 120 s.
`pl_missing` usuwa drugą kwestię. `fps` wydłuża czasy współczynnikiem 25 / (24000/1001) = 1001/960;
odwrotność 960/1001 skraca czasy. To dwa kierunki syntetycznej zmiany tempa.
Wzorce w `../golden/timings.json` zapisano niezależnie od generatora.

Testy integracyjne tworzą krótkie, lokalne klipy FFmpeg (kolor i tony), w tym
wideo bez audio, dwie ścieżki 440/880 Hz i opóźniony strumień. Pliki powstają
w katalogu tymczasowym; nie wymagają pobierania ani nie symulują jakości ASR.
Prawdziwe nagrania mowy PL/EN/JA nie są częścią tego korpusu i wymagają fazy 2.
