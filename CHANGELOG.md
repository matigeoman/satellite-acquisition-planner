# Changelog

Wszystkie istotne zmiany projektu są dokumentowane w tym pliku. Projekt stosuje
wersjonowanie zgodne z Semantic Versioning.

## [1.0.0-rc1] — 2026-07-17

### Dodano

- publiczne profile ICEYE i Pléiades Neo,
- pobieranie GP/OMM z CelesTrak i propagację SGP4,
- definiowanie AOI jako Point, Polygon i Rectangle,
- geometryczne okna dostępu oraz publiczny pipeline okazji akwizycyjnych,
- integrację prognozy zachmurzenia Open-Meteo dla sensorów EO,
- planowanie Greedy i CP-SAT ze wspólną funkcją celu,
- dynamiczne przeplanowanie z oknem zamrożonym,
- operacyjny globus Plotly i przestrzenną wizualizację orbit,
- walidację okien Access i raportów AER względem STK,
- dynamiczne czasy przeorientowania EO, ograniczenia ICEYE LEFT/RIGHT oraz
  maksymalny odstęp SAR–EO,
- automatyczne benchmarki Greedy kontra CP-SAT,
- przenośne archiwa projektów z kontrolą integralności,
- generator raportów HTML, DOCX, XLSX, JSON i CSV,
- audyt repozytorium `python -m app.cli audit`,
- dokumentację użytkownika, metodologiczną i deweloperską,
- workflow GitHub Actions dla testów, Ruff, kontroli danych i audytu.

### Zmieniono

- wersja aplikacji jest odczytywana z jednego pliku `VERSION`,
- testy odczytujące polskie teksty jawnie używają UTF-8,
- dokumentacja główna została ujednolicona i połączona indeksem.

### Ograniczenia wersji kandydującej

- okna dostępu są wynikiem modelu publicznego, a nie potwierdzeniem taskingu
  operatora,
- parametry ICEYE dotyczące manewrów są założeniami badawczymi,
- moduły historycznego renderera Cesium pozostają w repozytorium, ale nie są
  używane przez aktywną stronę globusa,
- STK służy do walidacji, a nie jest wymagany do podstawowego działania.
