# Ograniczenia i zakres interpretacji

1. Publiczne OMM/SGP4 nie odwzorowują pełnego procesu operacyjnego operatora.
2. Transformacja TEME → ITRF uwzględnia `UT1-UTC` i ruch bieguna z EOP, ale nie
   jest zamiennikiem precyzyjnej efemerydy operatora ani pełnej estymacji orbity.
3. Footprint sensora jest nominalnym prostokątem. Przecięcie z AOI jest liczone
   geometrycznie, lecz nie obejmuje pełnego modelu orientacji, terenu, krzywizny
   granic sceny i zastrzeżonych ograniczeń sensora.
4. Granice dostępu są doprecyzowywane numerycznie do tolerancji około 1 s;
   dokładność końcowa nadal zależy od jakości OMM, definicji ograniczeń i modelu
   sensora.
5. Zachmurzenie jest prognozą godzinową i może różnić się od warunków lokalnych.
6. Chmury wpływają na EO, ale nie blokują SAR.
7. Parametry manewrów ICEYE są założeniami badawczymi, nie danymi niejawnymi.
8. Interpolacja manewrowości Pléiades Neo upraszcza dynamikę ADCS.
9. Pamięć jest rozliczana dynamicznie na końcach akwizycji i kontaktów, ale nie
   odwzorowuje systemu plików, kompresji, pakietyzacji ani pełnej telemetrii.
10. Energia pozostaje modelem budżetowym; downlink nie ma jeszcze pełnego kosztu
    energii, temperatury ani orientacji anteny.
11. CP-SAT z limitem czasu może zwrócić rozwiązanie wykonalne bez dowodu optimum.
12. Hybrid zachowuje własny incumbent Greedy 2.0, ale nie gwarantuje optimum
    globalnego; jakość zależy od budowy i liczby sąsiedztw.
13. Graf konfliktów opisuje ograniczenia parowe. Pamięć, czas pracy i limity
    akwizycji pozostają ograniczeniami globalnymi planerów.
14. Profile preferencji są ważoną funkcją użyteczności, nie implementacją
    ELECTRE III lub TOPSIS.
15. STK może używać innego rekordu GP, EOP, modelu sił, epoki, układu odniesienia
    i definicji sensora; przypadki muszą być konfigurowane możliwie identycznie.
16. Okna kontaktów w scenariuszach demonstracyjnych są syntetyczne. Nie są
    potwierdzeniem widoczności, rezerwacji stacji ani dostępnej przepustowości.
17. Greedy stosuje deterministyczny przydział kontaktów FIFO; może odrzucić plan,
    dla którego istnieje lepszy globalny układ downlinków. CP-SAT jest modelem
    silniejszym, lecz nadal używa agregatowej objętości danych.
18. Wynik aplikacji nie jest potwierdzeniem rezerwacji komercyjnej ani wykonania
    akwizycji.

Źródła standardów, literatury i parametrów publicznych są zestawione w
[bibliografii projektu](references.md). Bibliografia nie zmienia statusu
parametrów oznaczonych jako założenia autorskie lub `MODEL_DERIVED`.
