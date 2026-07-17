# Benchmarking Greedy kontra CP-SAT

## Cel

Benchmark bada kompromis między czasem obliczeń a jakością harmonogramu.
Porównanie powinno używać identycznych zleceń, okazji, ograniczeń i funkcji celu.

## Zalecany plan eksperymentu

- rozmiary: 20, 50, 100, 200 i 500 zleceń,
- co najmniej 5 niezależnych ziaren dla analiz statystycznych,
- jeden wątek CP-SAT dla maksymalnej porównywalności,
- limity czasu: 1, 5, 10 i 30 sekund,
- osobny pomiar czasu budowy modelu i pracy solvera, jeżeli jest dostępny.

## Metryki

- czas całkowity,
- wartość funkcji celu,
- liczba i procent zrealizowanych zleceń,
- liczba pełnych par SAR–EO,
- wykorzystanie zasobów,
- przyczyny odrzuceń,
- względna poprawa CP-SAT względem Greedy.

## Interpretacja

Nie należy porównywać wyłącznie liczby akwizycji. Plan z mniejszą liczbą
akwizycji może realizować więcej zleceń obowiązkowych lub mieć wyższą jakość.
Status `UNKNOWN` albo błąd pojedynczego przebiegu powinien pozostać w danych,
a nie być usuwany bez śladu.
