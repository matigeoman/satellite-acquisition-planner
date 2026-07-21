# Satellite Acquisition Planner

**Wersja:** `1.1.0`

Satellite Acquisition Planner służy do planowania akwizycji zobrazowań
satelitarnych SAR i EO. Aplikacja łączy publiczne dane orbitalne OMM,
propagację SGP4, wyznaczanie okien dostępu, prognozę zachmurzenia, algorytmy
Greedy i CP-SAT, przeplanowanie oraz walidację względem STK.

Scenariusz `POLAND_DEMO` zawiera kompletny zestaw danych offline do prezentacji
i testów regresyjnych. Wyniki mają charakter badawczy: nie potwierdzają
komercyjnego taskingu ani wykonania akwizycji przez operatora.

## Najważniejsze funkcje

- profile 4 satelitów ICEYE i 2 satelitów Pléiades Neo;
- AOI typu Point, Polygon i Rectangle oraz import/eksport GeoJSON;
- OMM z CelesTrak, lokalny cache i propagacja SGP4;
- okna dostępu, ślady naziemne, globus operacyjny i mapa nieba;
- prognoza zachmurzenia Open-Meteo dla okazji EO;
- planowanie Greedy i OR-Tools CP-SAT ze wspólną funkcją celu;
- przeplanowanie z oknem zamrożonym i zakłóceniami operacyjnymi;
- benchmarki, raporty naukowe i walidacja względem STK;
- przenośne archiwa `.satplan.zip` z kontrolą integralności SHA-256.

## Szybki start — Docker

Docker jest najprostszą metodą uruchomienia kompletnego środowiska:

```powershell
docker compose up --build --detach
docker compose ps
```

Aplikacja jest dostępna pod adresem `http://localhost:8501`. Kontener powinien
osiągnąć status `healthy`.

Można też użyć skryptu:

```powershell
.\scripts\start_satplan.ps1
```

## Instalacja lokalna na Windows

Projekt jest walidowany referencyjnie na Pythonie 3.11. `uv` ani Conda nie są
wymagane.

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt -c .\requirements-lock.txt
python -m streamlit run .\streamlit_app.py
```

## CLI

```powershell
python -m app.cli check
python -m app.cli paths
python -m app.cli plan --scenario POLAND_DEMO --algorithm CP_SAT
python -m app.cli audit --strict
python -m app.cli health --skip-http
python -m app.cli release-check --algorithm BOTH --cp-sat-time-limit 2
```

## Kontrola jakości

```powershell
.\scripts\verify_release.ps1
```

Pełna kontrola z czystym buildem obrazu:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Skrypt uruchamia testy, Ruff, audyt repozytorium, healthcheck oraz scenariusz
E2E. Produkcyjny obraz Docker nie zawiera narzędzi deweloperskich takich jak
Pytest i Ruff; są instalowane przez `requirements-dev.txt`.

## Przepływ danych

```text
AOI i zlecenia
    ↓
OMM + SGP4
    ↓
okna dostępu i pogoda EO
    ↓
okazje akwizycyjne
    ↓
Greedy / CP-SAT
    ↓
harmonogram i przeplanowanie
    ↓
walidacja STK, archiwum projektu i raporty
```

## Struktura repozytorium

```text
app/models          modele domenowe i walidacja
app/integrations    orbity, dostęp, pogoda i STK
app/planning        Greedy, CP-SAT i ograniczenia
app/services        przypadki użycia
app/analysis        KPI, benchmarki i eksperymenty
app/projects        archiwa projektów
app/reporting       generowanie raportów
app/quality         audyt, healthcheck i kontrola E2E
app/tracking        topocentryka i predykcja przelotów
app/ui              interfejs Streamlit
app/visualization   wizualizacje Plotly
scripts             narzędzia uruchomieniowe i diagnostyczne
tests               testy jednostkowe, integracyjne i regresyjne
docs                dokumentacja techniczna i użytkowa
```

Szczegółowy opis znajduje się w
[`docs/project_structure.md`](docs/project_structure.md).

## Dokumentacja

- [indeks dokumentacji](docs/index.md),
- [instalacja](docs/installation.md),
- [instrukcja użytkownika](docs/user_guide.md),
- [architektura](docs/architecture.md),
- [model planowania](docs/planning_model.md),
- [źródła danych](docs/public_data_sources.md),
- [śledzenie satelitów](docs/live_tracking_and_sky_map.md),
- [walidacja STK](docs/stk_validation.md),
- [kontrola jakości](docs/quality_and_release.md),
- [ograniczenia modelu](docs/limitations.md),
- [informacje o wydaniu](RELEASE_NOTES.md).

## Ograniczenia interpretacyjne

OMM/SGP4, geometria sensora, parametry manewrowe i budżety zasobów są jawnymi
założeniami modelu. Zachmurzenie wpływa na EO, lecz nie na SAR. STK służy do
walidacji zewnętrznej i nie jest wymagany do podstawowego działania aplikacji.

## Wersjonowanie

Wersja aplikacji znajduje się w pliku [`VERSION`](VERSION). Historia zmian jest
prowadzona w [`CHANGELOG.md`](CHANGELOG.md).
