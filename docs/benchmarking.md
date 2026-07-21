# Benchmarking Greedy i CP-SAT

## Cel

Benchmark porównuje czas obliczeń i jakość harmonogramu dla identycznych
zleceń, okazji, ograniczeń oraz funkcji celu. Nie należy oceniać algorytmów
wyłącznie na podstawie liczby akwizycji: plan z mniejszą liczbą wpisów może
realizować więcej zleceń obowiązkowych albo uzyskać wyższą jakość.

## Scenariusze

Moduł korzysta z deterministycznie rozszerzanego scenariusza `STRESS`.
Obsługiwane rozmiary referencyjne to 20, 50, 100, 200 i 500 zleceń. Każde
zlecenie ma dziesięć okazji akwizycyjnych.

Zalecana konfiguracja eksperymentu:

- co najmniej 5 niezależnych ziaren dla analiz statystycznych;
- jeden wątek CP-SAT dla maksymalnej porównywalności;
- limity czasu 1, 5, 10 i 30 sekund;
- osobny pomiar czasu budowy modelu i pracy solvera, gdy jest dostępny;
- identyczna rezerwa pamięci i ten sam zestaw ograniczeń dynamicznych;
- wspólne ziarno CP-SAT dla wszystkich limitów czasu w obrębie tego samego powtórzenia; ziarno zmienia się dopiero między powtórzeniami.

## Rejestrowane metryki

- całkowity czas wykonania;
- status solvera;
- wartość funkcji celu;
- liczba i udział zrealizowanych zleceń;
- liczba akwizycji SAR i EO;
- liczba pełnych par SAR–EO;
- objętość danych i wykorzystanie zasobów;
- przyczyny odrzuceń;
- poprawa CP-SAT względem Greedy;
- szacowana liczba zmiennych boolowskich.

Status `UNKNOWN` lub błąd pojedynczego przebiegu pozostaje w wynikach i nie
przerywa całej serii.

## Interfejs i CLI

W aplikacji użyj modułu **Benchmarki**. Wersja CLI:

```powershell
python .\scripts\run_algorithm_benchmark.py `
    --request-counts 20 50 100 `
    --repetitions 5 `
    --cp-sat-limits 1 5 10 30 `
    --workers 1
```

Warianty 200 i 500 zleceń mogą wymagać zauważalnego czasu budowy modelu,
niezależnie od limitu pracy solvera.

## Eksport

Pakiet wynikowy zawiera:

- `benchmark_runs.csv`;
- `benchmark_pairs.csv`;
- `benchmark_summary.csv`;
- `benchmark_results.json`;
- `benchmark_charts.html`.
