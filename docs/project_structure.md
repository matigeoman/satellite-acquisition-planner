# Struktura projektu

```text
app/
├── analysis/    analiza KPI, diagnostyka, eksport i eksperymenty
├── config/      konfiguracja ścieżek i ustawień projektu
├── io/          wczytywanie i zapis modeli danych
├── models/      modele Pydantic i walidacja domenowa
├── planning/    Greedy, CP-SAT, konfiguracja i funkcja celu
├── scenarios/   generatory scenariuszy
├── services/    przypadki użycia i ich niezmienne kontrakty
└── ui/          interfejs Streamlit

data/
├── imports/stk/       przyszłe raporty STK
├── generated/         nowe wyniki robocze
├── reports/           zachowane raporty eksperymentalne
└── benchmarks/        zachowane benchmarki

scripts/         polecenia uruchomieniowe i diagnostyczne
tests/           testy jednostkowe, integracyjne i regresyjne
```

Zależności powinny przebiegać od warstwy prezentacji i usług w kierunku modeli
i planowania. Modele domenowe nie importują Streamlit, plików raportowych ani
konkretnych ścieżek systemu plików.


## Ważne podpakiety

```text
app/analysis/schedule/   analiza i eksport pojedynczego harmonogramu
app/services/contracts/ kontrakty wejścia i wyniku usług
```

Starsze moduły `schedule_report.py`, `planning_service.py`,
`replanning_service.py` i `comparison_service.py` nadal eksportują dotychczasowe
nazwy. Pozwala to refaktoryzować strukturę bez łamania istniejących skryptów i
testów.
