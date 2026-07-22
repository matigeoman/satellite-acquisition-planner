# Model danych

## Główne encje

```mermaid
classDiagram
    SystemCatalog "1" o-- "many" Satellite
    SystemCatalog "1" o-- "many" GroundStation
    Satellite "1" o-- "many" SensorMode
    ObservationRequest "1" --> "1" AOI
    ObservationRequest "1" --> "many" AcquisitionOpportunity
    Satellite "1" --> "many" AcquisitionOpportunity
    Satellite "1" --> "many" DownlinkOpportunity
    GroundStation "1" --> "many" DownlinkOpportunity
    AcquisitionOpportunity "many" --> "1" Schedule
    Schedule "1" o-- "many" ScheduleEntry
    Schedule "1" o-- "many" DownlinkScheduleEntry
    Schedule "1" o-- "many" MemoryTimelinePoint
    Schedule "1" o-- "many" SatelliteResourceSummary
    ScheduleEntry "1" --> "1" AcquisitionOpportunity
```

## Zlecenie obserwacyjne

Zlecenie opisuje AOI, priorytet, przedział czasowy, wymagania SAR/EO, status
aktywności i opcjonalny limit separacji czasowej dla pary SAR–EO.

## Okazja akwizycyjna

Okazja łączy zlecenie, satelitę, tryb sensora, przedział czasu, geometrię,
jakość, pokrycie, pamięć, czas pracy, pogodę EO oraz przyczyny wykonalności lub
niewykonalności.

## Stacja naziemna i okazja downlinku

`GroundStation` przechowuje położenie, minimalną elewację, aktywność i liczbę
równoległych kanałów. `DownlinkOpportunity` opisuje stały przedział kontaktu,
szybkość łącza, sprawność oraz czasy przygotowania i zakończenia. Zbiór
`DownlinkOpportunitySet` ma własny horyzont i jest walidowany względem katalogu.

## Zasoby w harmonogramie

`DownlinkScheduleEntry` zapisuje wykorzystany kontakt, nominalną i planistyczną
pojemność oraz identyfikatory danych rozliczonych FIFO. `MemoryTimelinePoint`
rejestruje każdą zmianę pamięci. `SatelliteResourceSummary` zawiera maksimum,
stan końcowy, objętość pozyskaną i przesłaną oraz informację o kompletności
dostawy.

## Harmonogram

Harmonogram zawiera wybrane okazje, status rozwiązania, wartość funkcji celu,
konfigurację algorytmu i metryki wykonania. Historia projektu przechowuje kolejne
wersje harmonogramu wraz z różnicami.

## Identyfikatory

Identyfikatory są stabilnymi ciągami domenowymi, np. `REQ-*`, `OPP-*`,
`DLO-*`, `GS-*`, `SCHEDULE-*`, `PROJECT-*`. Import projektu waliduje duplikaty i referencje.
