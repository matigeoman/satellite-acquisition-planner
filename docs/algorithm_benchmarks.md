# Benchmarki Greedy i CP-SAT

Moduł `Benchmarki algorytmów` wykonuje kontrolowaną serię eksperymentów
skalowalności dla 20, 50, 100, 200 i 500 zleceń. Scenariusze są
zagnieżdżone i powstają przez deterministyczne rozszerzanie scenariusza
`STRESS`. Każde zlecenie posiada dziesięć okazji akwizycji.

## Parametry

- liczba zleceń,
- liczba powtórzeń,
- jeden lub kilka limitów czasu CP-SAT,
- liczba wątków CP-SAT,
- ziarno losowe,
- rezerwa pamięci,
- włączenie dynamicznych ograniczeń operacyjnych.

## Rejestrowane wskaźniki

- czas obliczeń,
- wartość funkcji celu,
- liczba zrealizowanych i niezrealizowanych zleceń,
- liczba akwizycji SAR i EO,
- objętość danych,
- stopień realizacji zleceń,
- przyczyny odrzuceń,
- poprawa CP-SAT względem Greedy,
- szacowana liczba zmiennych boolowskich.

Błąd pojedynczego przebiegu lub status `UNKNOWN` nie przerywa całej serii.
Wynik zostaje zapisany jako nieudany przebieg i jest widoczny w zakładce
`Diagnostyka`.

## Eksport

Pakiet ZIP zawiera:

- `benchmark_runs.csv`,
- `benchmark_pairs.csv`,
- `benchmark_summary.csv`,
- `benchmark_results.json`,
- `benchmark_charts.html`.

## Uruchomienie bez Streamlit

```powershell
python .\scripts\run_algorithm_benchmark.py `
    --request-counts 20 50 100 `
    --repetitions 1 `
    --cp-sat-limits 2 10
```

Warianty 200 i 500 zleceń mogą wymagać zauważalnego czasu budowy modelu,
niezależnie od ustawionego limitu działania solvera.
