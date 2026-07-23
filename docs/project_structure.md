# Struktura projektu

## Katalog główny

```text
app/                 kod aplikacji
scripts/             polecenia uruchomieniowe i diagnostyczne
tests/               testy jednostkowe, integracyjne i regresyjne
data/                scenariusze, dane referencyjne i wyniki robocze
examples/             kompletne przykłady do prezentacji i walidacji
docs/                 dokumentacja
streamlit_app.py      punkt wejścia interfejsu
Dockerfile            definicja obrazu
docker-compose.yml    lokalne uruchomienie kontenera
VERSION               wersja aplikacji
```

## Pakiety aplikacji

```text
app/
├── analysis/         KPI, porównania, benchmarki i eksperymenty
├── catalogs/         jawne profile sensorów i satelitów
├── config/           ścieżki i ustawienia projektu
├── demo/             scenariusz demonstracyjny
├── geospatial/       geometria AOI i GeoJSON
├── integrations/     orbity, dostęp, pogoda i STK
│   ├── access/
│   ├── opportunities/
│   ├── orbits/
│   ├── stk_validation/
│   └── weather/
├── io/               odczyt i zapis modeli
├── models/           modele Pydantic i walidacja domenowa
├── planning/         Greedy, CP-SAT, Hybrid, graf, profile i ograniczenia
├── projects/         archiwa projektów i historia harmonogramów
├── quality/          audyt, healthcheck i kontrola E2E
├── reporting/        raporty HTML, DOCX i XLSX
├── scenarios/        generatory i warianty scenariuszy
├── services/         przypadki użycia i kontrakty
├── tracking/         topocentryka, oświetlenie i predykcja przelotów
├── ui/               interfejs Streamlit
└── visualization/    wizualizacje Plotly
```

## Dane

```text
data/
├── scenarios/            dane wejściowe EXAMPLE, POLAND_DEMO i STRESS
├── reference_schedules/  harmonogramy referencyjne
├── generated/            wyniki robocze i raporty
└── imports/stk/           raporty importowane z STK

examples/poland_demo/     samowystarczalny zestaw demonstracyjny offline
```

## Zasady zależności

Warstwa UI deleguje orkiestrację przypadków użycia do `app.services`.
Może jednocześnie korzystać z modeli domenowych, typów wynikowych i czystych
helperów prezentacyjnych. Serwisy koordynują planowanie, integracje i
raportowanie. Modele domenowe nie importują Streamlit ani konkretnych ścieżek
systemu plików.

Publiczne interfejsy pakietów są udostępniane przez pliki `__init__.py`.
Cienkie moduły `catalog_loader.py`, `request_loader.py`,
`opportunity_loader.py` i `schedule_loader.py` pozostają wyłącznie dla
zgodności wcześniejszych skryptów.
