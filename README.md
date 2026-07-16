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
- [`docs/io_and_paths.md`](docs/io_and_paths.md),
- [`docs/analysis_and_services.md`](docs/analysis_and_services.md),
- [`docs/public_orbits_sgp4.md`](docs/public_orbits_sgp4.md),
- [`docs/public_access_windows.md`](docs/public_access_windows.md).

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

## Publiczne orbity, okna dostępu i STK

Zakładka **Orbity publiczne** pobiera GP/OMM z CelesTrak, przechowuje je w
lokalnym cache i propaguje 4 obiekty ICEYE oraz 2 obiekty Pléiades Neo modelem
SGP4. Zakładka **Okna dostępu** łączy propagację z Point/Polygon, publicznymi
zakresami kątowymi sensorów, rozdzielczością, pokryciem i elewacją Słońca.

Wyniki są orientacyjnymi oknami geometrycznymi. STK pozostaje narzędziem do
walidacji wybranych przypadków, a nie jedynym źródłem działania aplikacji.
Szczegóły opisano w `docs/public_orbits_sgp4.md` oraz
`docs/public_access_windows.md`.

## Uporządkowany układ danych

Dane wejściowe znajdują się w `data/scenarios`, harmonogramy kontrolne w `data/reference_schedules`, a wyniki robocze w ignorowanym przez Git katalogu `data/generated`. Wszystkie ścieżki udostępnia `app.config.paths.ProjectPaths`.

Podstawowe polecenia terminalowe mają wspólny punkt wejścia:

```powershell
python -m app.cli check
python -m app.cli paths
python -m app.cli plan --scenario EXAMPLE --algorithm CP_SAT
```

Szczegóły opisano w `docs/data_layout_and_cli.md`.

## Publiczne profile i definiowanie celów

Zakładka **Cele i zlecenia** udostępnia profile ICEYE oraz Pléiades Neo,
rysowanie Point/Polygon/Rectangle na mapie, import/eksport GeoJSON i tworzenie
walidowanych zleceń. Parametry mają jawnie oznaczone pochodzenie. Orbity są
na tym etapie szablonami oczekującymi na aktualne OMM/TLE i propagację SGP4.
