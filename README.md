# Satellite Acquisition Planner

Aplikacja do planowania akwizycji zobrazowań satelitarnych wykonywanych przez
sensory SAR i optyczne EO. Projekt porównuje algorytm zachłanny z modelem
CP-SAT, obsługuje dynamiczne przeplanowanie, zakłócenia operacyjne i
powtarzalną walidację eksperymentalną.

## Najważniejsze funkcje

- konstelacja 4 satelitów SAR i 2 satelitów optycznych,
- zlecenia `SINGLE`, `DUAL_OPTIONAL` i `DUAL_REQUIRED`,
- planowanie Greedy i CP-SAT ze wspólną funkcją celu,
- ograniczenia czasu, pamięci, liczby akwizycji i konfliktów przejścia,
- zamrożone okno najbliższych operacji,
- przeplanowanie po awarii satelity, zmianie pogody i pilnym zleceniu,
- raporty CSV, wykresy i interfejs Streamlit,
- wielokrotne eksperymenty porównujące jakość i czas działania algorytmów.

## Architektura

```text
app/models      modele i walidacja danych
app/config      centralne ścieżki projektu
app/io          wczytywanie i zapis plików JSON
app/planning    algorytmy, konfiguracje i funkcja celu
app/services    przypadki użycia aplikacji
app/scenarios   generatory scenariuszy
app/analysis    KPI, raporty i eksperymenty
app/ui          moduły interfejsu Streamlit
scripts         skrypty uruchomieniowe i diagnostyczne
tests           testy jednostkowe i integracyjne
```

Dokumentacja techniczna:

- [`docs/project_structure.md`](docs/project_structure.md),
- [`docs/planning_architecture.md`](docs/planning_architecture.md),
- [`docs/ui_architecture.md`](docs/ui_architecture.md),
- [`docs/io_and_paths.md`](docs/io_and_paths.md).

## Instalacja

Projekt jest przygotowany dla Pythona 3.11.

```powershell
conda create -n satplan python=3.11
conda activate satplan
python -m pip install -r .\requirements-ui.txt
```

Zależności deweloperskie:

```powershell
python -m pip install -r .\requirements-dev.txt
```

## Testy i kontrola jakości

```powershell
pytest -q
ruff check app tests streamlit_app.py
python .\scripts\check_project.py
```

## Uruchomienie aplikacji

```powershell
streamlit run .\streamlit_app.py
```

Aplikacja udostępnia planowanie, porównanie Greedy–CP-SAT, dynamiczne
przeplanowanie, symulację zakłóceń oraz walidację eksperymentalną.

## Najważniejsze skrypty

```powershell
python .\scripts\run_greedy.py
python .\scripts\run_cp_sat.py
python .\scripts\run_replanning.py
python .\scripts\run_disruption_replanning.py
python .\scripts\run_experimental_validation.py
```

## Funkcja celu

Nagroda za priorytet i obowiązkowość jest naliczana raz na zrealizowane
zlecenie. Każda wybrana akwizycja wnosi dodatkowo ocenę jakości i pokrycia.
Dla `DUAL_REQUIRED` nagroda zlecenia jest przyznawana dopiero po wybraniu
zarówno obserwacji SAR, jak i optycznej.

## Dane orbitalne i STK

Obecne scenariusze wykorzystują syntetyczne okna akwizycyjne. Kolejny etap
integracji STK dostarczy okna wynikające z propagacji orbit i geometrii
obserwacji. STK będzie źródłem dostępności, natomiast aplikacja pozostanie
modułem optymalizacyjnym.
