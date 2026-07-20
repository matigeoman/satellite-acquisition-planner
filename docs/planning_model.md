# Model planowania

## Zmienna decyzyjna

Dla każdej wykonalnej okazji `i` tworzona jest zmienna binarna `x_i`, która
przyjmuje wartość 1, gdy okazja zostanie wybrana.

## Funkcja celu

Model maksymalizuje sumę:

- nagród za realizację zleceń i ich priorytet,
- jakości i pokrycia wybranych akwizycji,
- kar lub kosztów operacyjnych wynikających z konfiguracji.

Nagroda za `DUAL_REQUIRED` jest naliczana po wyborze zgodnej pary SAR i EO.

## Ograniczenia

- brak nakładania się operacji tego samego satelity,
- czas przeorientowania i stabilizacji,
- rezerwa pamięci,
- czas pracy sensora,
- limit liczby akwizycji,
- limity per modelowany przelot ICEYE,
- zgodność LEFT/RIGHT i kategorii trybu,
- maksymalna separacja SAR–EO,
- zamrożone operacje podczas przeplanowania.

## Greedy

Algorytm sortuje kandydatów według wspólnego scoringu i dodaje kolejne okazje,
jeżeli zachowują ograniczenia. Jest szybki i deterministyczny dla tej samej
konfiguracji.

## CP-SAT

Model OR-Tools CP-SAT rozwiązuje kombinatoryczny problem wyboru. Limit czasu,
liczba wątków i ziarno losowe są parametrami eksperymentu. Status `FEASIBLE`
nie oznacza dowodu optymalności.

## Przeplanowanie

```mermaid
flowchart LR
    A[Stary plan] --> B[EXECUTED]
    A --> C[FROZEN]
    A --> D[REPLANNABLE]
    E[Nowa pogoda lub zlecenie] --> F[Nowe okazje]
    D --> G[Greedy/CP-SAT]
    F --> G
    B --> H[Nowy plan]
    C --> H
    G --> H
```
