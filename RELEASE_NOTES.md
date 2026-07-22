# Satellite Acquisition Planner 1.2.0

Data wydania: **22 lipca 2026 r.**

Wersja 1.2.0 rozwija planer w kierunku jawnie udokumentowanej metody badawczej.
Nie zmienia formatu scenariuszy ani archiwów projektu, ale dodaje nowy algorytm,
warstwę grafową, profile decyzji i rozszerzony benchmark.

## Najważniejsze zmiany

### Graf niewykonalności

- każda wykonalna okazja może być węzłem grafu;
- krawędzie opisują alternatywy tego samego zlecenia, niezgodne pary SAR–EO i
  brak czasu na przeorientowanie;
- interfejs pokazuje gęstość, komponenty, przyczyny konfliktów i okazje o
  najwyższym stopniu.

### Greedy 2.0

- ranking uwzględnia rzadkość alternatywnych okien;
- kosztuje czas, pamięć i blokowanie wartościowych okazji innych zleceń;
- klasyczny Greedy pozostaje dostępny dla zgodności wyników historycznych.

### Planer Hybrid

- Greedy 2.0 tworzy rozwiązanie początkowe;
- CP-SAT optymalizuje kolejne sąsiedztwa zleceń wyznaczone z grafu;
- decyzje poza sąsiedztwem pozostają zablokowane;
- gorszy kandydat nie zastępuje incumbenta;
- CLI i release-check obsługują `HYBRID` oraz `ALL`.

### Profile decyzyjne

Dodano profile:

- `BALANCED`;
- `EMERGENCY`;
- `QUALITY_FIRST`;
- `THROUGHPUT`;
- `SAR_EO_FUSION`;
- `CUSTOM`.

Profile jawnie ustawiają wagi scoringu i heurystyki. Nie są deklarowane jako
pełna implementacja ELECTRE III lub TOPSIS.

### Benchmarki

- możliwe jest równoległe porównanie Greedy, CP-SAT i Hybrid;
- wszystkie warianty jednego powtórzenia używają tego samego ziarna;
- eksport zawiera dodatkowy plik
  `benchmark_algorithm_comparisons.csv`;
- osobno raportowane są wyniki CP-SAT i Hybrid względem Greedy.

### Dokumentacja naukowa

- dodano mapę źródło → implementacja → zakres adaptacji;
- rozbudowano bibliografię o prace Eddy’ego, Antuoriego i in., Xu i in.,
  Verfaillie i in., Vasegaarda i in., Globusa i in. oraz CCSDS;
- opisano, które elementy są autorskie, a które pozostają dopiero kierunkiem
  rozwoju;
- udokumentowano licencje analizowanych repozytoriów i brak kopiowania kodu.

## Podstawa metodologiczna

Szczegółowy opis znajduje się w:

- [`docs/research_foundations.md`](docs/research_foundations.md),
- [`docs/planning_model.md`](docs/planning_model.md),
- [`docs/scientific_methodology.md`](docs/scientific_methodology.md),
- [`docs/references.md`](docs/references.md).

## Walidacja referencyjna

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Oczekiwany wynik:

```text
Stan: RELEASE READY
Docker status: healthy
FINAL RELEASE 1.2.0: READY
```

## Zgodność

Wersja zachowuje:

- format scenariuszy i harmonogramów `1.0.x` i `1.1.x`;
- format archiwum projektu;
- publiczne interfejsy `app.io` i moduły zgodnościowe;
- scenariusze `EXAMPLE`, `POLAND_DEMO` i `STRESS`.

Nie jest wymagana migracja danych.

## Znane ograniczenia

- Hybrid gwarantuje zachowanie własnego incumbenta Greedy 2.0, ale nie optimum
  globalne;
- graf obejmuje konflikty parowe, a nie wszystkie ograniczenia zasobowe;
- profile są ważoną funkcją użyteczności, bez pełnego ELECTRE III;
- pamięć pozostaje modelem budżetowym bez planowania downlinku w czasie;
- OMM/SGP4 i parametry sensorów nie zastępują danych operatora.
