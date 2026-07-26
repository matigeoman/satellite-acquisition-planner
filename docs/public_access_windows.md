# Publiczne okna dostępu

Moduł **Okna dostępu** łączy publiczne elementy GP/OMM, propagację SGP4,
parametry EOP, publiczne profile sensorów ICEYE i Pléiades Neo oraz geometrię
zlecenia Point/Polygon/Rectangle w WGS 84.

## Zakres obliczeń

Dla każdego zgodnego satelity i trybu program oblicza w dyskretnych chwilach:

- pozycję satelity z SGP4 w TEME i ITRF/Earth Fixed,
- kąt off-nadir do reprezentatywnego punktu AOI,
- kąt padania przy powierzchni celu,
- stronę obserwacji LEFT/RIGHT/NADIR,
- zgodność z zakresem kątowym trybu i zlecenia,
- zgodność rozdzielczości,
- pokrycie Point/Polygon/Rectangle,
- elewację Słońca dla sensora optycznego.

Kolejne poprawne próbki są grupowane w okna. Gdy kalkulator ma dostęp do
propagatora SGP4, granice przejścia `nieważne ↔ ważne` są doprecyzowywane
bisekcją do tolerancji jednej sekundy. Tryb awaryjny bez propagatora używa
środka czasu między sąsiednimi próbkami i jawnie opisuje tę aproksymację.

## Pokrycie AOI

Dla poligonu program:

1. rozwija długości geograficzne przy przekroczeniu południka 180°,
2. wyznacza centroid geometrii z uwzględnieniem otworów,
3. tworzy lokalne odwzorowanie azymutalne równodystansowe WGS 84,
4. buduje nominalny prostokątny footprint sceny,
5. liczy rzeczywiste pole przecięcia `footprint ∩ AOI`,
6. sprawdza orientację 0° i 90° i wybiera większe pokrycie.

Wynik jest stosunkiem pola przecięcia do pola AOI. Model nadal używa
nominalnego prostokątnego footprintu, a nie pełnej chwilowej projekcji granic
sensora wynikającej z orientacji statku i modelu wysokościowego.

## Ograniczenia

Wynik nie jest potwierdzeniem dostępności komercyjnego taskingu. Publiczne OMM
nie zawierają informacji o stanie satelity, kolejce operatora, zasilaniu,
termice, pamięci ani zastrzeżonych regułach manewrowania.

Dla Pléiades Neo uwzględniana jest elewacja Słońca i prognoza zachmurzenia.
Prognoza jest niezależnym źródłem publicznym i nie zastępuje danych operatora
ani obserwacji meteorologicznej w chwili wykonania zdjęcia.

## Interfejs

Zakładka pokazuje:

- liczbę znalezionych okien,
- mapę AOI i fragmentów śladów naziemnych,
- oś czasu według satelity i trybu,
- tabelę kątów, pokrycia, epoki OMM i jakości danych,
- eksport JSON i CSV.
