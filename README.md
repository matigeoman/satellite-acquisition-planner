# Satellite Acquisition Planner

Aplikacja do planowania akwizycji zobrazowań satelitarnych wykonywanych przez
sensory SAR i optyczne. Projekt porównuje algorytm zachłanny z modelem CP-SAT,
obsługuje dynamiczne przeplanowanie, zakłócenia operacyjne i eksperymenty
porównawcze.

## Najważniejsze funkcje

- scenariusze z konstelacją 4 satelitów SAR i 2 satelitów optycznych,
- zlecenia `SINGLE`, `DUAL_OPTIONAL` i `DUAL_REQUIRED`,
- planowanie Greedy i CP-SAT,
- wspólna funkcja celu dla obu algorytmów,
- ograniczenia czasu, pamięci, liczby akwizycji i konfliktów przejścia,
- zamrożone okno najbliższych operacji,
- przeplanowanie po awarii satelity, zmianie pogody i pilnym zleceniu,
- raporty CSV, wykresy i interfejs Streamlit,
- powtarzalna walidacja eksperymentalna.

## Architektura

```text
app/models      modele i walidacja danych
app/planning    algorytmy, konfiguracje i wspólna funkcja celu
app/services    przypadki użycia aplikacji
app/scenarios   generatory scenariuszy
app/analysis    KPI, raporty i eksperymenty
app/ui          moduły interfejsu Streamlit
scripts         skrypty uruchomieniowe i diagnostyczne
tests           testy jednostkowe i integracyjne
```

Szczegóły warstwy planowania opisano w
[`docs/planning_architecture.md`](docs/planning_architecture.md), a interfejsu
w [`docs/ui_architecture.md`](docs/ui_architecture.md).

## Instalacja

Projekt został przygotowany dla Pythona 3.11.

```powershell
conda create -n satplan python=3.11
conda activate satplan
python -m pip install -r requirements-ui.txt
```

Zależności deweloperskie:

```powershell
python -m pip install -r requirements-dev.txt
```

## Testy i kontrola jakości

```powershell
pytest -q
ruff check app tests streamlit_app.py
```

## Uruchomienie aplikacji

```powershell
streamlit run .\streamlit_app.py
```

Aplikacja zawiera moduły planowania, porównania algorytmów, dynamicznego
przeplanowania, zakłóceń i walidacji eksperymentalnej.

## Skrypty

```powershell
python .\scripts
un_greedy.py
python .\scripts
un_cp_sat.py
python .\scripts
un_replanning.py
python .\scripts
un_disruption_replanning.py
python .\scripts
un_experimental_validation.py
```

## Funkcja celu

Nagroda za priorytet i obowiązkowość jest naliczana raz na zrealizowane
zlecenie. Każda wybrana akwizycja wnosi dodatkowo ocenę jakości i pokrycia.
Dla `DUAL_REQUIRED` nagroda zlecenia jest przyznawana dopiero po wybraniu
zarówno obserwacji SAR, jak i optycznej.

## Dane orbitalne

Obecne scenariusze wykorzystują syntetyczne okna akwizycyjne. Planowany etap
integracji STK dostarczy okna wynikające z propagacji orbit i geometrii
obserwacji. STK będzie źródłem dostępności, a aplikacja pozostanie modułem
optymalizacyjnym.
