# Publiczne okna dostępu

Moduł **Okna dostępu** łączy publiczne elementy GP/OMM, propagację SGP4,
publiczne profile sensorów ICEYE i Pléiades Neo oraz geometrię zlecenia
Point/Polygon w WGS84.

## Zakres obliczeń

Dla każdego zgodnego satelity i trybu program oblicza w dyskretnych chwilach:

- pozycję satelity z SGP4,
- kąt off-nadir do środka AOI,
- kąt padania przy powierzchni celu,
- stronę obserwacji LEFT/RIGHT/NADIR,
- zgodność z zakresem kątowym trybu i zlecenia,
- zgodność rozdzielczości,
- przybliżone pokrycie Point/Polygon,
- elewację Słońca dla sensora optycznego.

Kolejne poprawne próbki są łączone w ciągłe okna. Granice są aproksymowane
połową kroku propagacji. Mniejszy krok zwiększa rozdzielczość czasową, ale
wydłuża obliczenia.

## Pokrycie poligonu

Na obecnym etapie footprint trybu jest traktowany jako nominalny prostokąt.
Pokrycie Polygon jest szacowane przez porównanie wymiarów jego bounding box
z szerokością i długością nominalnej sceny. Sprawdzane są dwie orientacje
prostokąta, a program wybiera korzystniejszą.

To założenie jest jawnie oznaczone jako modelowe. W kolejnych etapach można je
zastąpić dokładnym przecięciem footprintu sensora z AOI.

## Ograniczenia

Wynik nie jest potwierdzeniem dostępności komercyjnego taskingu. Publiczne OMM
nie zawierają informacji o stanie satelity, kolejce operatora, zasilaniu,
termice, pamięci i zastrzeżonych regułach manewrowania.

Dla Pléiades Neo uwzględniana jest elewacja Słońca, ale nie jest jeszcze
pobierana prognoza zachmurzenia. Następny etap połączy okna geometryczne z
prognozą pogody i utworzy pełne `AcquisitionOpportunity` dla algorytmów Greedy
i CP-SAT.

## Interfejs

Zakładka pokazuje:

- liczbę znalezionych okien,
- mapę AOI i fragmentów śladów naziemnych,
- oś czasu według satelity i trybu,
- tabelę kątów, pokrycia i epoki OMM,
- eksport JSON i CSV.
