# Satellite Acquisition Planner

**Wersja:** `1.0.1`

Satellite Acquisition Planner jest aplikacją badawczo-inżynierską do planowania
akwizycji zobrazowań satelitarnych SAR i EO. Łączy dane orbitalne OMM,
propagację SGP4, geometryczne okna dostępu, prognozę zachmurzenia, algorytmy
Greedy i CP-SAT, przeplanowanie oraz walidację względem STK.

Projekt działa lokalnie albo w kontenerze Docker. Scenariusz `POLAND_DEMO`
zawiera kompletny zestaw danych offline do prezentacji i testów regresyjnych.

## Zakres funkcjonalny

### Dane i geometria

- profile 4 satelitów ICEYE i 2 satelitów Pléiades Neo;
- AOI typu Point, Polygon i Rectangle oraz import/eksport GeoJSON;
- pobieranie OMM z CelesTrak, lokalna pamięć podręczna i propagacja SGP4;
- okna dostępu, ślady naziemne, mapa nieba i predykcja AOS/MAX/LOS;
- zachmurzenie Open-Meteo uwzględniane dla okazji EO.

### Planowanie

- zlecenia `SINGLE`, `DUAL_OPTIONAL` i `DUAL_REQUIRED`;
- wspólna funkcja celu dla Greedy i OR-Tools CP-SAT;
- ograniczenia zasobów, manewrów, trybów obrazowania i par SAR–EO;
- przeplanowanie z oknem zamrożonym i odświeżeniem danych pogodowych;
- benchmarki oraz porównanie jakości i czasu działania algorytmów.

### Wyniki i walidacja

- globus operacyjny i wizualizacje Plotly;
- import raportów Access/AER z STK;
- przenośne archiwa `.satplan.zip` z manifestem SHA-256;
- raporty HTML, DOCX, XLSX, JSON, CSV i PNG;
- audyt repozytorium, test E2E, GitHub Actions i healthcheck Dockera.

## Szybki start

Projekt jest walidowany referencyjnie na Pythonie 3.11.

```powershell
conda create -n satplan python=3.11
conda activate satplan
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt
python -m streamlit run .\streamlit_app.py
```

Uruchomienie przez Docker:

```powershell
.\scripts\start_satplan.ps1
```

Domyślny adres aplikacji: `http://localhost:8501`.

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

Pełna kontrola lokalna:

```powershell
.\scripts\verify_release.ps1
```

Kontrola z czystym buildem obrazu:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Skrypt wykonuje testy, linting, audyt, healthcheck, pełny scenariusz E2E oraz
kontrole wewnątrz kontenera.

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

## Struktura

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

Pełny opis znajduje się w [`docs/project_structure.md`](docs/project_structure.md).

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

## Zakres interpretacji

Wyniki są rezultatami modelu opartego na danych publicznych. Nie potwierdzają
komercyjnej dostępności satelity, rezerwacji taskingu ani wykonania akwizycji.
Parametry manewrowe i budżety zasobów są jawnymi założeniami badawczymi.
Zachmurzenie wpływa na EO, lecz nie na SAR. STK służy do walidacji i nie jest
wymagany do podstawowego działania aplikacji.

## Wersjonowanie

Bieżąca wersja znajduje się w pliku [`VERSION`](VERSION). Historia zmian jest
prowadzona w [`CHANGELOG.md`](CHANGELOG.md).
