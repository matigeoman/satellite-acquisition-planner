# Prognoza zachmurzenia i publiczne okazje planistyczne

## Cel modułu

Moduł rozszerza geometryczne okna dostępu o prognozę zachmurzenia dla
Pléiades Neo, a następnie konwertuje wyniki do domenowego modelu
`AcquisitionOpportunity`, który jest bezpośrednio obsługiwany przez Greedy i
CP-SAT.

## Źródło pogody

Aplikacja korzysta z Open-Meteo Forecast API i pobiera godzinowe zmienne:

- `cloud_cover`,
- `cloud_cover_low`,
- `cloud_cover_mid`,
- `cloud_cover_high`.

Zapytania używają współrzędnych WGS84, czasu UTC i dyskowego cache w
`data/generated/weather`. Cache ma domyślną ważność jednej godziny. W razie
błędu sieci aplikacja może użyć ostatniej zapisanej odpowiedzi i oznacza ją
jako nieaktualną.

## Próbkowanie AOI

Dla punktu wykonywane jest jedno zapytanie. Dla poligonu program wybiera do
dziewięciu punktów reprezentujących obszar:

- środek poligonu, jeżeli leży wewnątrz,
- wybrane wierzchołki,
- punkty siatki wewnątrz bounding box.

Użytkownik wybiera sposób agregacji zachmurzenia:

- maksimum — wariant konserwatywny,
- 75. percentyl,
- średnia.

Prognoza godzinowa jest interpolowana liniowo do czasu `peak_utc` okna.
Wykonalność EO jest oceniana przez porównanie wyniku z
`request.max_cloud_cover`.

## Konwersja do AcquisitionOpportunity

Dla każdego okna program:

1. wybiera minimalny czas akwizycji wymagany przez tryb,
2. centruje akwizycję wokół najlepszego momentu okna,
3. przypisuje geometrię, pokrycie i parametry obserwacji,
4. dodaje zachmurzenie i elewację Słońca dla EO,
5. oblicza rozmiar danych jako `czas × data_rate_mb_s`,
6. wyznacza ocenę jakości,
7. oznacza okazję jako wykonalną albo niewykonalną.

Okazje EO przekraczające limit chmur są zachowywane w zbiorze z powodem
niewykonalności. Solvery automatycznie używają wyłącznie okazji wykonalnych.

## Planowanie publiczne

Zakładka **Planowanie publiczne** scala okazje utworzone dla kilku zleceń w
jeden scenariusz sesyjny i uruchamia istniejące implementacje Greedy albo
CP-SAT. Używany katalog zawiera 4 sloty ICEYE i 2 sloty Pléiades Neo.

Dane orbitalne i profile sensorów są publiczne, natomiast następujące
parametry pozostają jawnymi założeniami modelowymi:

- pojemność i początkowe zajęcie pamięci,
- minimalny czas przejścia między akwizycjami,
- limit liczby akwizycji na dobę,
- limit czasu obrazowania na dobę.

## Ograniczenia

- prognoza nie gwarantuje rzeczywistego zachmurzenia w chwili akwizycji,
- rozdzielczość modeli pogodowych jest mniejsza niż rozdzielczość obrazu EO,
- ocena poligonu opiera się na ograniczonej liczbie punktów,
- okna orbitalne i sensorowe są modelem publicznym, nie potwierdzeniem
  komercyjnego taskingu operatora.
