# Ograniczenia i zakres interpretacji

1. Publiczne OMM/SGP4 nie odwzorowują pełnego procesu operacyjnego operatora.
2. Footprint sensora i dostępność są uproszczeniem geometrycznym.
3. Zachmurzenie jest prognozą godzinową i może różnić się od warunków lokalnych.
4. Chmury wpływają na EO, ale nie blokują SAR.
5. Parametry manewrów ICEYE są założeniami badawczymi, nie danymi niejawnymi.
6. Interpolacja manewrowości Pléiades Neo upraszcza dynamikę ADCS.
7. Pamięć i energia są modelami budżetowymi, bez pełnej telemetrii platformy.
8. CP-SAT z limitem czasu może zwrócić rozwiązanie wykonalne bez dowodu optimum.
9. Hybrid zachowuje własny incumbent Greedy 2.0, ale nie gwarantuje optimum
   globalnego; jakość zależy od budowy i liczby sąsiedztw.
10. Graf konfliktów opisuje ograniczenia parowe. Pamięć, czas pracy i limity
    akwizycji pozostają ograniczeniami globalnymi planerów.
11. Profile preferencji są ważoną funkcją użyteczności, nie implementacją
    ELECTRE III lub TOPSIS.
12. STK może używać innego modelu sił, epoki i definicji sensora; przypadki muszą
   być konfigurowane możliwie identycznie.
13. Wynik aplikacji nie jest potwierdzeniem rezerwacji komercyjnej ani wykonania
    akwizycji.


Źródła standardów, literatury i parametrów publicznych są zestawione w
[bibliografii projektu](references.md). Bibliografia nie zmienia statusu
parametrów oznaczonych jako założenia autorskie lub `MODEL_DERIVED`.
