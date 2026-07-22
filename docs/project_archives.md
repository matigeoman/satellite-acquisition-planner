# Przenośne projekty SatPlan

Moduł **Projekty** zapisuje stan operacyjny aplikacji do jednego
archiwum ZIP. Import jest transakcyjny: bieżąca sesja jest zmieniana dopiero po
sprawdzeniu struktury ZIP, wersji schematu, sum SHA-256 oraz relacji domenowych.

## Zapisywane komponenty

Zależnie od dostępnego stanu archiwum może zawierać:

- `metadata.json` i `manifest.json`,
- `aoi.geojson`,
- `requests.json`,
- `orbit_snapshot.json` z surowymi rekordami OMM,
- `access_windows.json`,
- `opportunity_builds.json`, `weather_assessments.json` i `opportunities.json`,
- `scenario.json`, `planning_result.json`, `schedule.json` i opcjonalny
  `downlinks.json`,
- `schedule_history.json` oraz `replanning_history.json`,
- `public_replanning_result.json`,
- `benchmark_config.json` i `benchmark_results.json`.

Snapshot orbit i prognozy jest zapisem danych użytych w obliczeniach, dlatego
po imporcie nie jest automatycznie zastępowany nowszym stanem źródeł publicznych.

## Odtwarzalność

Archiwum przechowuje konfigurację solvera, seed CP-SAT/benchmarku, harmonogram,
publiczne OMM, oceny zachmurzenia, stacje i okna downlinku oraz wersję schematu. Analiza harmonogramu jest
po imporcie obliczana ponownie z odtworzonego katalogu, zbioru zleceń, okazji i
harmonogramu.

## Bezpieczeństwo importu

Importer ogranicza rozmiar archiwum, liczbę plików i rozmiar po rozpakowaniu.
Odrzuca ścieżki absolutne, `..`, duplikaty nazw, brakujące pliki wymagane,
niezgodne sumy kontrolne oraz niespójne identyfikatory zleceń i okazji.
