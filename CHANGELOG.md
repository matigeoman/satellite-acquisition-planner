# Changelog

Wszystkie istotne zmiany projektu są dokumentowane w tym pliku. Projekt stosuje
wersjonowanie zgodne z Semantic Versioning.

## [1.0.0] — 2026-07-20

### Wydanie stabilne

- zakończono walidację pełnego pipeline'u AOI → OMM/SGP4 → access → pogoda EO → okazje → Greedy/CP-SAT → przeplanowanie → archiwum projektu → raport;
- potwierdzono działanie scenariusza `POLAND_DEMO`, mapy nieba, śledzenia satelitów, trybu offline i kontenera Docker;
- ujednolicono wersję aplikacji, obrazu Docker, Compose, workflow CI i dokumentacji do `1.0.0`;
- dodano `RELEASE_NOTES.md` oraz skrypt `scripts/verify_release.ps1` do powtarzalnej walidacji wydania;
- rozszerzono kontrolę GitHub Actions o oba algorytmy planowania i kontrolę wydania wewnątrz kontenera;
- usunięto tymczasową instrukcję hotfixa i przypadkowo śledzony raport DOCX z katalogu głównego;
- zaostrzono audyt i skrypt sprzątający, aby ponownie nie dopuścić takich artefaktów do wydania.

### Zgodność i ograniczenia

- referencyjne środowisko: Python 3.11;
- dane OMM/SGP4, geometria sensorów, pogoda i parametry manewrowe pozostają modelami badawczymi opisanymi w `docs/limitations.md`;
- wynik planera nie stanowi potwierdzenia komercyjnego taskingu ani wykonania akwizycji.

## [1.0.0-rc4] — 2026-07-20

### Dodano

- wymuszone odświeżanie OMM, które omija świeży cache i nadal zachowuje fallback offline;
- ranking przelotów 0–100 oraz klasy jakości: bardzo dobry, dobry, graniczny i słaby;
- czas przelotu powyżej 10° i szacowany czas widoczności optycznej;
- filtry jakości, widoczności oraz powiązania z oknami access i harmonogramem;
- panel pochodzenia danych OMM, wieku cache i ostrzeżeń o starej epoce;
- przełączniki warstw mapy Ziemi: ground track, footprint i terminator.

### Zmieniono

- test wydania waliduje wyniki jakości i metryki utwardzonego live trackingu;
- obraz Docker i dokumentacja używają wersji `1.0.0-rc4`.

## [1.0.0-rc3] — 2026-07-20

### Dodano

- moduł śledzenia satelitów na żywo z lokalną mapą nieba azymut–elewacja,
- predykcję przelotów AOS/MAX/LOS nad wybranym obserwatorem,
- globalną mapę pozycji z ground trackiem, terminatorem i referencyjnym footprintem,
- tryb czasu rzeczywistego oraz symulację `1×`, `10×` i `60×`,
- ocenę wieku OMM i uproszczoną widoczność optyczną,
- integrację śledzenia z oknami access i harmonogramem planera,
- referencyjny plik `live_tracking_reference.json` dla Poland Demo,
- gotowy scenariusz demonstracyjny Polski działający bez sieci,
- polecenie `python -m app.cli release-check` wykonujące test E2E,
- skrypt porządkujący repozytorium i usuwający artefakty etapów.

### Usunięto

- nieaktywny renderer Cesium, jego testy, dokumentację i teksturę zastępczą,
- robocze notatki etapów z finalnej struktury repozytorium.

### Zmieniono

- scenariusz demonstracyjny rozszerzono do 48 godzin, 50 zleceń i 500 okazji,
- demo ładuje zapisany snapshot OMM i referencyjne okna dostępu offline,
- globus operacyjny otrzymał neutralną kolorystykę, a AOI polygonowe są
  rysowane jako obrysy, bez wypełnienia zasłaniającego całą kulę Ziemi,
- kontrola wydania waliduje OMM, próbną propagację SGP4 i access przed
  planowaniem Greedy/CP-SAT,
- audyt wymaga czystego repozytorium bez śledzonych paczek, instalatorów i kopii roboczych,
- wersję kandydującą podniesiono do `1.0.0-rc3`.

## [1.0.0-rc2] — 2026-07-17

### Dodano

- wieloetapowy `Dockerfile` oparty na Pythonie 3.11,
- `docker-compose.yml` z trwałymi wolumenami, healthcheckiem i portem
  konfigurowanym przez `SATPLAN_PORT`,
- skrypty PowerShell i BAT do uruchamiania oraz zatrzymywania aplikacji,
- polecenie `python -m app.cli health`, które sprawdza Streamlit, CP-SAT, dane
  referencyjne i możliwość zapisu,
- workflow GitHub Actions budujący i testujący obraz kontenera,
- dokumentację wdrożenia, eksportu danych z wolumenów i diagnostyki.

### Zmieniono

- audyt repozytorium kontroluje teraz kompletność konfiguracji Docker,
- obraz działa jako nieuprzywilejowany użytkownik `satplan`,
- wersję kandydującą podniesiono do `1.0.0-rc2`.

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
