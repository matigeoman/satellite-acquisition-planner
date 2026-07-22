# Benchmarking Greedy, CP-SAT i Hybrid

## Cel

Benchmark porównuje czas obliczeń i jakość harmonogramu dla identycznych
zleceń, okazji, ograniczeń, profilu decyzyjnego i funkcji celu. Liczba
akwizycji nie jest samodzielną miarą jakości: plan z mniejszą liczbą wpisów
może realizować więcej zleceń obowiązkowych albo uzyskać wyższą jakość.

## Warianty

- `GREEDY` — plan bazowy;
- `CP-SAT <limit>` — globalna optymalizacja z limitem czasu;
- `HYBRID <limit>` — Greedy 2.0 i lokalne sąsiedztwa CP-SAT.

Hybrid jest opcjonalny w kontrakcie programistycznym
`AlgorithmBenchmarkConfig(include_hybrid=True)` i domyślnie włączony w
interfejsie wersji 1.3.0.

## Scenariusze

Moduł korzysta z deterministycznie rozszerzanego scenariusza `STRESS`.
Obsługiwane rozmiary referencyjne to 20, 50, 100, 200 i 500 zleceń. Każde
zlecenie ma dziesięć okazji akwizycyjnych.

Zalecana konfiguracja:

- co najmniej 5 niezależnych powtórzeń;
- jeden wątek solvera;
- limity czasu 1, 5, 10 i 30 sekund;
- identyczna rezerwa pamięci, zbiór okien downlinku i model przeorientowania;
- wspólne ziarno dla Greedy, CP-SAT i Hybrid w jednym powtórzeniu;
- osobne raportowanie statusów solvera;
- zapis wersji aplikacji i OR-Tools.

## Rejestrowane metryki

- czas wykonania;
- status solvera i harmonogramu;
- funkcja celu;
- liczba i udział zrealizowanych zleceń;
- realizacja zleceń obowiązkowych;
- liczba akwizycji SAR i EO;
- objętość danych i średnia jakość;
- przyczyny odrzuceń;
- poprawa CP-SAT i Hybrid względem Greedy;
- szacowana liczba zmiennych boolowskich.

Błąd pojedynczego przebiegu pozostaje w eksporcie i nie przerywa całej serii.

## Interpretacja Hybrid

Właściwość `Hybrid >= Greedy 2.0` dotyczy planu początkowego zbudowanego
wewnątrz Hybrid. W tabeli benchmarkowej `GREEDY` może działać z innym trybem
heurystyki, dlatego do formalnej kontroli gwarancji służy również test
jednostkowy porównujący Hybrid z `HybridPlannerConfig.greedy_config()`.

## Interfejs i CLI

W aplikacji użyj modułu **Benchmarki** i zaznacz wariant Hybrid. Skrypt CLI:

```powershell
python .\scripts\run_algorithm_benchmark.py `
    --request-counts 20 50 100 `
    --repetitions 5 `
    --cp-sat-limits 1 5 10 30 `
    --workers 1
```

Skrypt zachowuje zgodność ze starszym benchmarkiem Greedy–CP-SAT. Pełny
benchmark trzech metod jest dostępny z interfejsu i API serwisu.

## Eksport

Pakiet wynikowy zawiera:

- `benchmark_runs.csv` — wszystkie przebiegi;
- `benchmark_pairs.csv` — zgodnościowe porównania CP-SAT–Greedy;
- `benchmark_algorithm_comparisons.csv` — CP-SAT i Hybrid względem Greedy;
- `benchmark_summary.csv` — agregaty;
- `benchmark_results.json` — konfigurację i surowe rekordy;
- `benchmark_charts.html` — wykresy interaktywne.
