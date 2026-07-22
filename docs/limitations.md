# Ograniczenia i zakres interpretacji

1. Publiczne OMM/SGP4 nie odwzorowują pełnego procesu operacyjnego operatora.
2. Footprint sensora i dostępność są uproszczeniem geometrycznym.
3. Zachmurzenie jest prognozą godzinową i może różnić się od warunków lokalnych.
4. Chmury wpływają na EO, ale nie blokują SAR.
5. Parametry manewrów ICEYE są założeniami badawczymi, nie danymi niejawnymi.
6. Interpolacja manewrowości Pléiades Neo upraszcza dynamikę ADCS.
7. Pamięć jest rozliczana dynamicznie na końcach akwizycji i kontaktów, ale nie
   odwzorowuje systemu plików, kompresji, pakietyzacji ani pełnej telemetrii.
8. Energia pozostaje modelem budżetowym; downlink nie ma jeszcze kosztu energii,
   temperatury ani orientacji anteny.
9. CP-SAT z limitem czasu może zwrócić rozwiązanie wykonalne bez dowodu optimum.
10. Hybrid zachowuje własny incumbent Greedy 2.0, ale nie gwarantuje optimum
   globalnego; jakość zależy od budowy i liczby sąsiedztw.
11. Graf konfliktów opisuje ograniczenia parowe. Pamięć, czas pracy i limity
    akwizycji pozostają ograniczeniami globalnymi planerów. Dynamiczna pamięć jest sprawdzana w
    osobnym modelu zdarzeniowym.
12. Profile preferencji są ważoną funkcją użyteczności, nie implementacją
    ELECTRE III lub TOPSIS.
13. STK może używać innego modelu sił, epoki i definicji sensora; przypadki muszą
   być konfigurowane możliwie identycznie.
14. Wynik aplikacji nie jest potwierdzeniem rezerwacji komercyjnej ani wykonania
    akwizycji.


Źródła standardów, literatury i parametrów publicznych są zestawione w
[bibliografii projektu](references.md). Bibliografia nie zmienia statusu
parametrów oznaczonych jako założenia autorskie lub `MODEL_DERIVED`.

15. Okna kontaktów w scenariuszach demonstracyjnych są syntetyczne. Nie są
    potwierdzeniem widoczności, rezerwacji stacji ani dostępnej przepustowości.
16. Greedy stosuje deterministyczny przydział kontaktów FIFO; może odrzucić plan,
    dla którego istnieje lepszy globalny układ downlinków. CP-SAT jest modelem
    silniejszym, lecz nadal używa agregatowej objętości danych.
