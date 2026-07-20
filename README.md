# Satellite Acquisition Planner

**Wersja:** `1.0.0-rc3`

Aplikacja do wielokryterialnego planowania akwizycji zobrazowań satelitarnych
SAR i optycznych EO. Łączy publiczne dane orbitalne, propagację SGP4,
geometryczne okna dostępu, prognozę zachmurzenia, algorytm Greedy, model CP-SAT,
dynamiczne przeplanowanie, walidację STK i eksport wyników naukowych.

## Najważniejsze funkcje

- publiczna konstelacja modelowa: 4 satelity ICEYE i 2 Pléiades Neo,
- AOI jako Point, Polygon lub Rectangle oraz import/eksport GeoJSON,
- GP/OMM z CelesTrak, cache i propagacja SGP4,
- geometryczne okna dostępu oraz trajektorie na globusie Plotly,
- zachmurzenie Open-Meteo dla okazji EO,
- zlecenia `SINGLE`, `DUAL_OPTIONAL` i `DUAL_REQUIRED`,
- planowanie Greedy i CP-SAT ze wspólną funkcją celu,
- dynamiczne manewry EO, przejścia ICEYE LEFT/RIGHT i limit SAR–EO,
- przeplanowanie z oknem zamrożonym i odświeżeniem pogody,
- import Access/AER i porównanie wyników z STK,
- benchmarki skalowalności Greedy kontra CP-SAT,
- przenośne archiwa `.satplan.zip` z manifestem SHA-256,
- raporty HTML, DOCX, XLSX, JSON, CSV i PNG,
- audyt repozytorium oraz automatyczna kontrola GitHub Actions,
- obraz Docker, healthcheck i uruchamianie jednym poleceniem,
- gotowy scenariusz demonstracyjny Polski i końcowa kontrola E2E wydania.

## Instalacja

Projekt jest walidowany referencyjnie na Pythonie 3.11.

```powershell
conda create -n satplan python=3.11
conda activate satplan
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt
```

Pełna instrukcja: [`docs/installation.md`](docs/installation.md).

Uruchomienie przez Docker:

```powershell
.\scripts\start_satplan.ps1
```

Dokumentacja kontenera: [`docs/docker.md`](docs/docker.md).

## Uruchomienie

```powershell
streamlit run .\streamlit_app.py
```

Tryb CLI:

```powershell
python -m app.cli check
python -m app.cli paths
python -m app.cli plan --scenario EXAMPLE --algorithm CP_SAT
python -m app.cli audit
python -m app.cli health --skip-http
python -m app.cli release-check --algorithm GREEDY
```

## Kontrola jakości

```powershell
pytest -q
ruff check app tests streamlit_app.py scripts
python -m app.cli check
python -m app.cli audit
python -m app.cli health --skip-http
```

Raport audytu w JSON:

```powershell
python -m app.cli audit `
    --json .\data\generated\reports\project_audit.json
```

Workflow `.github/workflows/quality.yml` wykonuje te kontrole po każdym pushu i
pull requeście na Pythonie 3.11. Workflow `.github/workflows/docker.yml` buduje
obraz i wykonuje test uruchomieniowy kontenera.

## Typowy przepływ

```text
AOI i zlecenia
    ↓
publiczne OMM + SGP4
    ↓
okna dostępu
    ↓
pogoda EO i okazje
    ↓
Greedy / CP-SAT
    ↓
harmonogram i przeplanowanie
    ↓
STK, benchmarki, archiwum projektu i raport
```

## Struktura

```text
app/models          modele domenowe i walidacja
app/config          centralne ścieżki
app/io              zapis i odczyt danych
app/integrations    orbity, access, pogoda i STK
app/planning        Greedy, CP-SAT i ograniczenia
app/services        przypadki użycia
app/analysis        KPI, porównania i eksperymenty
app/projects        archiwa projektów
app/reporting       HTML, DOCX, XLSX i dane źródłowe
app/quality         audyt repozytorium, środowiska i kontrola E2E
app/demo            deterministyczny scenariusz prezentacyjny
app/ui              interfejs Streamlit
app/visualization   wizualizacje Plotly
scripts             skrypty uruchomieniowe
tests               testy jednostkowe i integracyjne
docs                dokumentacja
```

## Dokumentacja

Pełny indeks: [`docs/index.md`](docs/index.md).

Najważniejsze rozdziały:

- [instrukcja użytkownika](docs/user_guide.md),
- [architektura](docs/architecture.md),
- [model danych](docs/data_model.md),
- [model planowania](docs/planning_model.md),
- [publiczne źródła danych](docs/public_data_sources.md),
- [metodyka naukowa](docs/scientific_methodology.md),
- [benchmarking](docs/benchmarking.md),
- [walidacja STK](docs/stk_validation.md),
- [ograniczenia modelu](docs/limitations.md),
- [przewodnik deweloperski](docs/developer_guide.md),
- [kontrola jakości i wydania](docs/quality_and_release.md),
- [rozwiązywanie problemów](docs/troubleshooting.md),
- [Docker i wdrożenie](docs/docker.md),
- [demo i kontrola wydania](docs/demo_and_release_check.md).

## Zakres interpretacji

Okna dostępu i harmonogram są wynikiem modelu opartego na danych publicznych.
Nie potwierdzają dostępności komercyjnej, rezerwacji taskingu ani wykonania
akwizycji przez operatora. Zachmurzenie wpływa na EO, nie na SAR. Parametry
operacyjne ICEYE dotyczące manewrów są jawnymi założeniami badawczymi. STK jest
narzędziem walidacji i nie jest wymagany do podstawowego działania aplikacji.

## Wersjonowanie

Źródłem wersji jest plik [`VERSION`](VERSION). Historia zmian znajduje się w
[`CHANGELOG.md`](CHANGELOG.md).
