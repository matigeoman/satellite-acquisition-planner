# Satellite Acquisition Planner 1.0.0 — informacje o wydaniu

Data wydania: **20 lipca 2026 r.**

## Zakres

Wersja `1.0.0` jest pierwszym stabilnym wydaniem aplikacji do planowania akwizycji satelitarnych SAR i EO. Łączy definiowanie AOI i zleceń, publiczne dane OMM, propagację SGP4, geometryczne okna dostępu, pogodę EO, budowanie okazji, planowanie Greedy i CP-SAT, przeplanowanie, walidację STK, benchmarki oraz raportowanie naukowe.

## Najważniejsze elementy

- scenariusz `POLAND_DEMO`: 48 godzin, 6 satelitów, 50 zleceń i 500 okazji;
- planowanie `SINGLE`, `DUAL_OPTIONAL` i `DUAL_REQUIRED`;
- Greedy i OR-Tools CP-SAT ze wspólną funkcją celu;
- dynamiczne przeplanowanie z oknem zamrożonym;
- mapa operacyjna, globus 3D Plotly i mapa nieba azymut–elewacja;
- predykcja przelotów AOS/MAX/LOS, ranking jakości oraz analiza wieku OMM;
- działanie demonstracyjne offline bez CelesTrak i Open-Meteo;
- import Access/AER i porównanie ze STK;
- eksport projektu i raporty HTML, DOCX, XLSX, JSON, CSV i PNG;
- Docker, healthcheck, GitHub Actions i automatyczna kontrola wydania.

## Referencyjna walidacja

Przed utworzeniem taga należy uruchomić na Pythonie 3.11:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Kontrola wykonuje:

1. pełny zestaw testów `pytest`;
2. Ruff;
3. kontrolę scenariuszy;
4. ścisły audyt UTF-8, zależności, struktury i czystości repozytorium;
5. healthcheck runtime;
6. E2E dla Greedy i CP-SAT;
7. opcjonalny czysty build obrazu Docker;
8. audyt, healthcheck i kontrolę E2E wewnątrz kontenera.

Oczekiwany wynik końcowy:

```text
Stan: RELEASE READY
Docker status: healthy
```

## Instalacja

### Python 3.11

```powershell
conda create -n satplan python=3.11
conda activate satplan
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt
python -m streamlit run .\streamlit_app.py
```

### Docker

```powershell
.\scripts\start_satplan.ps1
```

Domyślny adres: `http://localhost:8501`.

## Tryb offline

Scenariusz `POLAND_DEMO` zawiera lokalny snapshot OMM, okna dostępu, okazje, harmonogramy, benchmark i walidację STK. Może zostać wczytany bez dostępu do CelesTrak i Open-Meteo. Dane online są opcjonalne i korzystają z cache oraz jawnych komunikatów o wieku danych.

## Znane ograniczenia

- publiczne OMM/SGP4 nie odwzorowują pełnego procesu operacyjnego operatora;
- footprint i dostępność są modelami geometrycznymi;
- pogoda EO jest prognozą godzinową;
- parametry manewrowe i budżety zasobów są założeniami badawczymi;
- wynik aplikacji nie jest potwierdzeniem rezerwacji ani wykonania komercyjnej akwizycji.

Pełny wykaz: [`docs/limitations.md`](docs/limitations.md).

## Utworzenie taga

Tag tworzy się dopiero po pozytywnej kontroli paczki finalnej i czystym `git status`:

```powershell
git tag -a v1.0.0 -m "Satellite Acquisition Planner 1.0.0"
git push origin v1.0.0
```
