# Changelog

Wszystkie istotne zmiany projektu są dokumentowane w tym pliku. Projekt stosuje
wersjonowanie zgodne z Semantic Versioning.

## [Unreleased]

Brak zmian po wydaniu 1.3.0.

## [1.3.0] — 2026-07-22

### Pamięć i downlink

- dodano modele stacji naziemnych i jawnych okien kontaktu satelita–stacja;
- akwizycje zwiększają zajętość pamięci w chwili zakończenia, a transmisje
  zmniejszają ją po zakończeniu kontaktu;
- dodano przepustowość, sprawność łącza, czasy setup/teardown oraz rezerwę
  pojemności downlinku;
- Greedy, CP-SAT i Hybrid mogą planować akwizycje razem z transmisją danych;
- CP-SAT uwzględnia dynamiczne ograniczenia pamięci, dostępność danych przed
  kontaktem, konflikty anteny satelity i liczbę kanałów stacji;
- opcjonalnie można wymagać opróżnienia pamięci do końca horyzontu.

### Interfejs, eksport i scenariusze

- dodano zakładkę z wykresem zajętości pamięci, tabelą kontaktów i zdarzeniami
  zasobów;
- harmonogram JSON, raporty, KPI i archiwa projektu zachowują kontakty,
  podsumowania zasobów oraz identyfikatory przesłanych danych;
- scenariusze `EXAMPLE`, `STRESS` i `POLAND_DEMO` zawierają syntetyczne okna
  downlinku dla dwóch demonstracyjnych stacji naziemnych;
- generator scenariusza stresowego zapisuje również `downlinks.json`;
- CLI otrzymało parametry planowania downlinku i rezerwy przepustowości.

### Dokumentacja i walidacja

- dodano opis modelu dynamicznej pamięci, założeń czasowych i ograniczeń;
- rozszerzono mapowanie źródeł naukowych o zintegrowane planowanie akwizycji,
  pamięci i transmisji;
- kontrola wydania weryfikuje podsumowania pamięci oraz dane downlinku;
- dodano testy modeli stacji, okien kontaktu, kanałów stacji, rezerwy łącza,
  profilu pamięci i eksportu danych.

## [1.2.0] — 2026-07-22

### Planowanie

- dodano graf niewykonalności okazji z przyczynami konfliktów i komponentami;
- dodano Greedy 2.0 uwzględniający rzadkość okien, koszt zasobów i koszt
  blokowanych okazji;
- dodano planer Hybrid: Greedy jako incumbent i lokalna poprawa CP-SAT;
- CP-SAT obsługuje hints oraz ustalenie decyzji poza lokalnym sąsiedztwem;
- dodano profile decyzyjne `BALANCED`, `EMERGENCY`, `QUALITY_FIRST`,
  `THROUGHPUT`, `SAR_EO_FUSION` i `CUSTOM`.

### Benchmarki i interfejs

- benchmark może porównywać Greedy, CP-SAT i Hybrid przy wspólnych seedach;
- eksport zawiera ogólną tabelę porównań wszystkich challengerów z Greedy;
- wyniki planowania pokazują diagnostykę grafu konfliktów;
- CLI i kontrola wydania obsługują `HYBRID` i tryb `ALL`.

### Dokumentacja

- dodano mapowanie metod na konkretne publikacje i repozytoria referencyjne;
- rozdzielono adaptacje naukowe, elementy autorskie i przyszłe kierunki;
- rozszerzono bibliografię oraz opis metodyki eksperymentalnej;
- podniesiono wersję aplikacji i zasobów wydaniowych do `1.2.0`.

## [1.1.0] — 2026-07-21

### Interfejs

- ujednolicono wygląd aplikacji, panel boczny, nawigację, metryki, formularze,
  zakładki i tabele;
- przebudowano globus operacyjny: dodano wyróżnianie satelity, centrowanie na
  Polsce, Europie lub wybranym obiekcie oraz czytelniejsze warstwy i etykiety;
- rozszerzono widok śledzenia o przełączanie mapy globalnej i globusa,
  wyróżnione ground tracki oraz czytelniejszy układ parametrów;
- poprawiono zachowanie interfejsu na węższych ekranach i ograniczono puste
  przestrzenie między sekcjami.

### Benchmarki i wyniki

- benchmark używa wspólnego ziarna CP-SAT dla wszystkich limitów czasu w obrębie
  danego powtórzenia;
- wykresy dla pojedynczego rozmiaru problemu używają osi kategorialnej zamiast
  zakresu liczbowego 99–101;
- diagnostyka odrzuceń prezentuje zagregowane, skumulowane przyczyny według
  wariantu algorytmu;
- przeplanowanie pokazuje jednoznaczny komunikat, gdy aktywny filtr nie zawiera
  zmian;
- podgląd archiwum poprawnie liczy okazje zapisane w aktywnym wyniku i ostrzega,
  gdy harmonogram obejmuje tylko część zleceń projektu.

### Repozytorium i wydanie

- podniesiono wersję aplikacji do `1.1.0` we wszystkich zasobach wydaniowych;
- uproszczono README i instrukcję instalacji, wskazując Docker jako podstawową
  metodę uruchomienia;
- oddzielono narzędzia deweloperskie od zależności obrazu produkcyjnego;
- dodano plik z referencyjnymi wersjami bezpośrednich zależności;
- zastąpiono historyczne nazwy plików roboczych ogólnymi regułami sprzątania i
  audytu;
- usunięto nieaktualną informację o pozostawionym kodzie Cesium.

### Zgodność

- formaty scenariuszy, harmonogramów i archiwów projektu pozostają zgodne z
  wersją `1.0.1`;
- migracja danych nie jest wymagana.

## [1.0.1] — 2026-07-20

### Uporządkowano

- pogrupowano nawigację aplikacji według przepływu operacyjnego, analizy i
  zarządzania projektem;
- ujednolicono nazwy modułów, komunikaty i terminologię w interfejsie;
- zaktualizowano dokumentację struktury projektu i usunięto dwa powielone
  rozdziały;
- usunięto nieużywany plik `main.py` oraz nieużywane importy;
- dodano `.editorconfig` i `.gitattributes` dla spójnego UTF-8 oraz zakończeń
  linii;
- rozszerzono linting i audyt repozytorium o kontrolę zbędnych importów i plików
  historycznych.

### Zgodność

- formaty scenariuszy, harmonogramów i archiwów projektu pozostają zgodne z
  `1.0.0`;
- algorytmy planowania i dane referencyjne nie zostały zmienione.

## [1.0.0] — 2026-07-20

### Wydanie stabilne

- zakończono walidację pełnego pipeline'u AOI → OMM/SGP4 → access → pogoda EO →
  okazje → Greedy/CP-SAT → przeplanowanie → archiwum projektu → raport;
- potwierdzono działanie scenariusza `POLAND_DEMO`, mapy nieba, śledzenia
  satelitów, trybu offline i kontenera Docker;
- ujednolicono wersję aplikacji, obrazu Docker, Compose, workflow CI i
  dokumentacji;
- dodano `RELEASE_NOTES.md` oraz skrypt `scripts/verify_release.ps1` do
  powtarzalnej walidacji wydania;
- rozszerzono kontrolę GitHub Actions o oba algorytmy planowania i kontrolę
  wydania wewnątrz kontenera.

### Zgodność i ograniczenia

- referencyjne środowisko: Python 3.11;
- dane OMM/SGP4, geometria sensorów, pogoda i parametry manewrowe pozostają
  modelami badawczymi opisanymi w `docs/limitations.md`;
- wynik planera nie stanowi potwierdzenia komercyjnego taskingu ani wykonania
  akwizycji.

## [1.0.0-rc4] — 2026-07-20

### Dodano

- wymuszone odświeżanie OMM, które omija świeży cache i zachowuje fallback
  offline;
- ranking przelotów 0–100 oraz klasy jakości;
- czas przelotu powyżej 10° i szacowany czas widoczności optycznej;
- filtry jakości, widoczności oraz powiązania z oknami access i harmonogramem;
- panel pochodzenia danych OMM, wieku cache i ostrzeżeń o starej epoce;
- przełączniki warstw mapy Ziemi: ground track, footprint i terminator.

### Zmieniono

- test wydania waliduje wyniki jakości i metryki live trackingu;
- obraz Docker i dokumentacja używają wersji `1.0.0-rc4`.

## [1.0.0-rc3] — 2026-07-20

### Dodano

- moduł śledzenia satelitów na żywo z lokalną mapą nieba azymut–elewacja;
- predykcję przelotów AOS/MAX/LOS nad wybranym obserwatorem;
- globalną mapę pozycji z ground trackiem, terminatorem i referencyjnym
  footprintem;
- tryb czasu rzeczywistego oraz symulację `1×`, `10×` i `60×`;
- ocenę wieku OMM i uproszczoną widoczność optyczną;
- integrację śledzenia z oknami access i harmonogramem planera;
- referencyjny plik `live_tracking_reference.json` dla Poland Demo;
- gotowy scenariusz demonstracyjny Polski działający bez sieci;
- polecenie `python -m app.cli release-check` wykonujące test E2E;
- skrypt porządkujący repozytorium i usuwający artefakty robocze.

### Usunięto

- nieaktywny renderer Cesium, jego testy, dokumentację i teksturę zastępczą;
- robocze notatki etapów z finalnej struktury repozytorium.

### Zmieniono

- scenariusz demonstracyjny rozszerzono do 48 godzin, 50 zleceń i 500 okazji;
- demo ładuje zapisany snapshot OMM i referencyjne okna dostępu offline;
- globus operacyjny otrzymał neutralną kolorystykę, a AOI polygonowe są rysowane
  jako obrysy;
- kontrola wydania waliduje OMM, próbną propagację SGP4 i access przed
  planowaniem Greedy/CP-SAT;
- audyt wymaga czystego repozytorium bez śledzonych paczek, instalatorów i kopii
  roboczych.

## [1.0.0-rc2] — 2026-07-17

### Dodano

- wieloetapowy `Dockerfile` oparty na Pythonie 3.11;
- `docker-compose.yml` z trwałymi wolumenami, healthcheckiem i portem
  konfigurowanym przez `SATPLAN_PORT`;
- skrypty PowerShell i BAT do uruchamiania oraz zatrzymywania aplikacji;
- polecenie `python -m app.cli health` sprawdzające Streamlit, CP-SAT, dane
  referencyjne i możliwość zapisu;
- workflow GitHub Actions budujący i testujący obraz kontenera;
- dokumentację wdrożenia, eksportu danych z wolumenów i diagnostyki.

## [1.0.0-rc1] — 2026-07-17

### Dodano

- publiczne profile ICEYE i Pléiades Neo;
- pobieranie GP/OMM z CelesTrak i propagację SGP4;
- definiowanie AOI jako Point, Polygon i Rectangle;
- geometryczne okna dostępu oraz publiczny pipeline okazji akwizycyjnych;
- integrację prognozy zachmurzenia Open-Meteo dla sensorów EO;
- planowanie Greedy i CP-SAT ze wspólną funkcją celu;
- dynamiczne przeplanowanie z oknem zamrożonym;
- operacyjny globus Plotly i przestrzenną wizualizację orbit;
- walidację okien Access i raportów AER względem STK;
- dynamiczne czasy przeorientowania EO, ograniczenia ICEYE LEFT/RIGHT oraz
  maksymalny odstęp SAR–EO;
- automatyczne benchmarki Greedy kontra CP-SAT;
- przenośne archiwa projektów z kontrolą integralności;
- generator raportów HTML, DOCX, XLSX, JSON i CSV;
- audyt repozytorium `python -m app.cli audit`;
- dokumentację użytkownika, metodologiczną i deweloperską;
- workflow GitHub Actions dla testów, Ruff, kontroli danych i audytu.

### Ograniczenia wersji kandydującej

- okna dostępu są wynikiem modelu publicznego, a nie potwierdzeniem taskingu
  operatora;
- parametry ICEYE dotyczące manewrów są założeniami badawczymi;
- STK służy do walidacji, a nie jest wymagany do podstawowego działania.
