# Satellite Acquisition Planner 1.4.0

Data wydania: **26 lipca 2026 r.**

Wersja 1.4.0 porządkuje warstwę orbitalną i usuwa najważniejsze uproszczenia
w transformacji ram odniesienia, wyznaczaniu granic okien oraz obliczaniu
pokrycia poligonu. Zmiany nie oznaczają dostępu do efemeryd operatorskich —
planer nadal pracuje na publicznych OMM/GP i modelu SGP4 — ale jawnie opisuje
jakość danych i zachowuje reprodukowalny zestaw regresyjny względem STK 13.

## Najważniejsze zmiany 1.4.0

- transformacja TEME → ITRF2020 wykorzystuje interpolowane parametry EOP
  (`UT1-UTC`, ruch bieguna `xp/yp`) i jawnie oznacza dane obserwowane,
  predykcyjne albo tryb przybliżony;
- dodano parser, cache i twardy limit wieku pliku EOP;
- granice okien dostępu są doprecyzowywane bisekcją SGP4 do tolerancji 1 s;
- pokrycie Polygon jest liczone z rzeczywistego przecięcia AOI i footprintu
  w lokalnym odwzorowaniu WGS 84;
- poprawiono centroidy geometrii z otworami i przecinających południk 180°;
- cache OMM starszy niż 72 h jest odrzucany bez jawnego wymuszenia;
- dodano cztery poziomy świeżości danych orbitalnych;
- dodano domyślny, reprodukowalny tryb `PINNED` oraz eksploracyjny tryb
  `LIVE`;
- snapshoty i archiwa zapisują tryb wyboru oraz przypięte numery NORAD;
- CI egzekwuje coverage, Pyright, rozszerzony Ruff i `pip-audit`;
- zależność `GitPython` ma minimalną bezpieczną wersję 3.1.55;
- Dependabot sprawdza zależności Python, Docker i GitHub Actions;
- numer wersji obrazu Docker pochodzi z pliku `VERSION`;
- ograniczono podwójne uruchamianie workflow i dodano anulowanie starszych
  przebiegów dla tej samej gałęzi;
- dodano regresję numeryczną TEME → ITRF2020 dla ICEYE-X82 i Pléiades Neo 3
  względem efemeryd STK 13.

## Walidacja techniczna

Zestaw referencyjny w `tests/fixtures/stk_validation/` zawiera próbki TEME,
ITRF2020 oraz EOP dla 19–20 lipca 2026 r. Test transformacji ma tolerancję
2 cm. Dane służą kontroli regresji kodu; nie są deklaracją dokładności
publicznego OMM względem rzeczywistej orbity.

## Zachowany model z wersji 1.3.0

Dla każdego satelity tworzona jest oś zdarzeń:

```text
stan początkowy pamięci
    ↓
koniec akwizycji: +objętość danych
    ↓
koniec downlinku: −objętość wysłanych danych
    ↓
kolejne akwizycje i kontakty
```

Plan jest wykonalny tylko wtedy, gdy zajętość pamięci nie przekracza limitu
planistycznego w żadnym punkcie tej osi. Opcjonalnie można wymagać, aby dane
zostały w całości przesłane przed końcem horyzontu.

## Nowe elementy domenowe

- `GroundStation` — lokalizacja, minimalna elewacja, aktywność i liczba
  równoległych kanałów odbiorczych;
- `DownlinkOpportunity` — stałe okno kontaktu, przepustowość, sprawność,
  setup/teardown i nominalna pojemność transmisji;
- `DownlinkOpportunitySet` — zwalidowany zbiór kontaktów zgodny z katalogiem i
  horyzontem scenariusza;
- `DownlinkScheduleEntry` — wybrane okno, zaplanowana objętość i identyfikatory
  danych przesłanych metodą FIFO;
- `MemoryTimelinePoint` i `SatelliteResourceSummary` — ślad zdarzeń oraz
  podsumowanie szczytowej, końcowej i przesłanej objętości danych.

## Planery

### Greedy

Greedy chronologicznie przydziela dostępne kontakty do danych znajdujących się
już w pamięci. Przy każdej próbie dodania akwizycji sprawdza cały wynikowy
profil pamięci. Dzięki temu może zaakceptować łączną objętość akwizycji większą
od fizycznej pojemności pamięci, o ile wcześniejsze downlinki zwalniają miejsce.

### CP-SAT

CP-SAT otrzymał zmienne użycia kontaktu i ilości przesyłanych danych. Model
uwzględnia:

- pojemność kontaktu po odjęciu rezerwy;
- dostępność danych przed rozpoczęciem kontaktu;
- pamięć w kolejnych punktach czasowych;
- jeden kontakt na antenę satelity;
- liczbę równoległych kanałów stacji;
- opcjonalny zakaz jednoczesnego obrazowania i downlinku;
- opcjonalne opróżnienie pamięci do końca horyzontu.

### Hybrid

Hybrid przekazuje ten sam model pamięci i kontaktów do planu początkowego
Greedy oraz lokalnych podproblemów CP-SAT. Zachowuje dotychczasową zasadę
nieprzyjmowania gorszego incumbenta przy równym statusie wykonalności.

## Interfejs i eksport

Strona planowania zawiera sekcję **Pamięć dynamiczna i downlink** oraz zakładkę
**Pamięć i downlink**. Dostępne są:

- wykres zajętości pamięci w czasie;
- podsumowania dla każdego satelity;
- lista wybranych kontaktów i wykorzystanie ich pojemności;
- identyfikatory danych przesłanych w każdym kontakcie;
- eksport akwizycji i downlinków do oddzielnych plików CSV;
- pełny zapis zasobów w harmonogramie JSON i archiwum `.satplan.zip`.

CLI obsługuje:

```text
--enable-downlink
--require-full-downlink
--allow-simultaneous-imaging-downlink
--downlink-capacity-reserve-ratio
```

## Scenariusze demonstracyjne

`EXAMPLE`, `STRESS` i `POLAND_DEMO` zawierają po dwie demonstracyjne stacje
oraz odpowiednio 36, 36 i 72 okna kontaktu. Okna są **syntetyczne**. Służą do
walidacji algorytmu i nie reprezentują rzeczywistego dostępu operatorskiego,
licencji częstotliwościowej ani umowy z właścicielem stacji.

## Podstawa naukowa

Rozszerzenie jest autorską implementacją inspirowaną zintegrowanym modelem
akwizycji, pamięci i downlinku opisanym przez Antuoriego, Wojtowicza i
Hebrarda, modelami Mission Planning and Scheduling CCSDS oraz literaturą
Satellite Range Scheduling. Nie skopiowano kodu z repozytoriów referencyjnych.
Szczegóły znajdują się w:

- `docs/research_foundations.md`;
- `docs/downlink_and_dynamic_memory.md`;
- `docs/references.md`.

## Zgodność

- stare katalogi bez `ground_stations` pozostają poprawne;
- stare harmonogramy bez wpisów downlinku pozostają poprawne;
- schemat archiwum projektu pozostaje `1.0.0`, ale scenariusz wewnątrz archiwum
  może zawierać opcjonalny `downlink_set`;
- planowanie downlinku jest wyłączone domyślnie na poziomie API dla zgodności,
  a w głównym formularzu scenariuszy wbudowanych jest włączone;
- Nie jest wymagana migracja danych.

## Kontrola wydania

Pełną walidację wydania uruchamia skrypt:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Równoważne kroki ręczne:

```powershell
docker compose build --pull --no-cache satplan

docker compose run --rm --user root `
  -e PIP_NO_CACHE_DIR=1 `
  satplan sh -lc "python -m pip install --quiet --no-cache-dir -r requirements-dev.txt -c requirements-lock.txt && python -m pytest -q && python -m ruff check app tests streamlit_app.py scripts"

docker compose up -d --force-recreate satplan
docker compose exec -T satplan python -m app.cli audit --strict
docker compose exec -T satplan python -m app.cli release-check --algorithm ALL --cp-sat-time-limit 2
```

Oczekiwane zakończenie skryptu wydania:

```text
FINAL RELEASE 1.4.0: READY
```
