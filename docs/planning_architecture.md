# Architektura warstwy planowania

## Odpowiedzialności modułów

- `config.py` — konfiguracje Greedy i CP-SAT oraz ich walidacja.
- `scoring.py` — wspólna funkcja celu i rozdzielanie wkładów na wpisy.
- `fixed.py` — definicja akwizycji `FROZEN` i `EXECUTED`.
- `greedy.py` — deterministyczne konstruowanie harmonogramu krok po kroku.
- `cp_sat.py` — model całkowitoliczbowy, ograniczenia i mapowanie wyniku solvera.

Publiczny interfejs pozostaje dostępny przez `app.planning`, dzięki czemu
warstwa usług nie zależy od wewnętrznego rozmieszczenia klas.

## Wspólna funkcja celu

Dla zlecenia `r` nagroda jest wyznaczana jako:

```text
priority(r) × priority_weight
+ mandatory_bonus, gdy zlecenie jest obowiązkowe
```

Dla każdej akwizycji `o`:

```text
quality_score(o) × quality_weight
+ coverage_ratio(o) × coverage_weight
```

Zasady naliczania:

1. `SINGLE` — nagroda zlecenia i ocena jednej akwizycji.
2. `DUAL_REQUIRED` — nagroda zlecenia tylko po wybraniu kompletu SAR + EO;
   wkład nagrody jest dzielony pomiędzy dwa wpisy.
3. `DUAL_OPTIONAL` — pierwsza akwizycja otrzymuje nagrodę zlecenia, a druga
   wyłącznie ocenę akwizycji i premię za uzupełnienie pary.

Wspólny moduł `scoring.py` eliminuje ryzyko rozbieżności punktacji między
Greedy i CP-SAT.

## Skalowanie w CP-SAT

CP-SAT przyjmuje całkowite współczynniki. Wartości funkcji celu i zasobów są
skalowane według `objective_scale` oraz `resource_scale`. Po rozwiązaniu modelu
wkłady harmonogramu są ponownie obliczane w jednostkach zmiennoprzecinkowych,
co zapewnia czytelne raportowanie bez utraty spójności modelu.

## Stabilność interfejsu

Klasy konfiguracyjne są zdefiniowane w `config.py`, lecz nadal można je
importować ze zgodnych ścieżek:

```python
from app.planning.greedy import GreedyPlannerConfig
from app.planning.cp_sat import CpSatPlannerConfig
```

Preferowany nowy import:

```python
from app.planning import GreedyPlannerConfig, CpSatPlannerConfig
```
