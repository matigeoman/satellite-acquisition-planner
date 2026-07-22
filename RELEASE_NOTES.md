# Satellite Acquisition Planner 1.3.0

Data wydania: **22 lipca 2026 r.**

Wersja 1.3.0 rozszerza planer o zintegrowane planowanie akwizycji, pamięci
pokładowej i transmisji danych do stacji naziemnych. Rozszerzenie zachowuje
model Hybrid z wersji 1.2.0, ale usuwa wcześniejsze uproszczenie, w którym
pamięć była wyłącznie sumarycznym budżetem na cały horyzont.

## Najważniejsza zmiana

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
docker compose build --no-cache satplan

docker compose run --rm --user root `
  -e PIP_NO_CACHE_DIR=1 `
  satplan sh -lc "python -m pip install --quiet --no-cache-dir -r requirements-dev.txt -c requirements-lock.txt && python -m pytest -q && python -m ruff check app tests streamlit_app.py scripts"

docker compose up -d --force-recreate satplan
docker compose exec -T satplan python -m app.cli audit --strict
docker compose exec -T satplan python -m app.cli release-check --algorithm ALL --cp-sat-time-limit 2
```

Oczekiwane zakończenie skryptu wydania:

```text
FINAL RELEASE 1.3.0: READY
```
