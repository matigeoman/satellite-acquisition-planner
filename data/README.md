# Katalog danych

Katalog `data` zawiera dane wejściowe, wyniki referencyjne oraz artefakty
wygenerowane przez skrypty i aplikację.

## Dane wejściowe

Pliki `example_*.json` tworzą scenariusz podstawowy, a `stress_*.json`
scenariusz przeciążony. Każdy scenariusz składa się z:

- katalogu systemu i satelitów,
- zbioru zleceń,
- zbioru okazji akwizycyjnych.

## Wyniki referencyjne

Pliki `*_schedule_greedy.json` oraz `*_schedule_cp_sat.json` są harmonogramami
referencyjnymi używanymi przez interfejs i testy regresyjne.

## Wyniki generowane

- `reports/` — raporty CSV i wykresy z dotychczasowych eksperymentów,
- `benchmarks/` — zapisane wyniki benchmarków,
- `generated/` — docelowe miejsce nowych wyników generowanych podczas pracy,
- `imports/stk/` — raporty dostępności eksportowane ze STK.

Wewnętrzne wskaźniki udziałowe są przechowywane w zakresie `0–1`. Dopiero
warstwa interfejsu formatuje je jako wartości procentowe `0–100%`.
