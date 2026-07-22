# Podstawy naukowe, inspiracje i źródła

Dokument rozdziela cztery rodzaje podstaw projektu:

1. **standardy implementacyjne** — formaty danych, propagacja, układy
   odniesienia i wymiana informacji;
2. **literaturę problemu planowania** — definicje problemu, ograniczenia,
   metody rozwiązania i zasady eksperymentów;
3. **publiczne materiały operatorów i dostawców** — jawne profile
   demonstracyjne i dane środowiskowe;
4. **repozytoria referencyjne** — przykłady organizacji eksperymentów lub
   implementacji pokrewnych modeli.

Satellite Acquisition Planner jest implementacją autorską. Kod analizowanych
repozytoriów nie został skopiowany. Wersja 1.3.0 rozwija wcześniejszą warstwę badawczą o zintegrowane
planowanie pamięci i downlinku: akwizycje generują dane, kontakty ze stacjami
zwalniają pamięć, a planery respektują przepustowość i liczbę kanałów stacji.
Pozostałe adaptowane koncepcje obejmują graf niewykonalności, heurystykę kosztu
utraconych okazji, Greedy jako rozwiązanie początkowe i lokalną poprawę
CP-SAT oraz jawne profile preferencji. Dokładne mapowanie znajduje się w
[`research_foundations.md`](research_foundations.md).

## Powiązanie źródeł z elementami aplikacji

| Element projektu | Podstawa | Sposób wykorzystania |
|---|---|---|
| OMM/GP | [R1], [R2] | format i interpretacja publicznych elementów orbitalnych |
| propagacja SGP4 | [R3] | model propagacji zgodny z rodziną SGP4/SDP4 |
| układy odniesienia | [R4], [R5] | punkt odniesienia dla WGS 84 i transformacji niebieski–ziemski |
| klasyfikacja AEOSSP | [R6]–[R9] | definicja klasy problemu, typowe ograniczenia i rodziny metod |
| dyskretne okazje i graf konfliktów | [R17], [R26] | węzły jako okazje oraz krawędzie jako parowe konflikty niewykonalności |
| Greedy 2.0 | [R19] | adaptacja idei korzyści systemowej i kosztu utraconych okazji |
| Hybrid Greedy–CP-SAT | [R18] | rozwiązanie początkowe Greedy i lokalna poprawa wybranych sąsiedztw |
| profile preferencji | [R21], [G2] | jawne profile wag; bez deklarowania pełnej implementacji ELECTRE III |
| reaktywne przeplanowanie | [R20], [R22] | zachowanie wpisów wykonanych i zamrożonych oraz ponowna optymalizacja |
| dynamiczna pamięć i downlink | [R18], [R22], [R28], [G1] | agregatowa objętość danych, okna kontaktów, przepustowość i limity kanałów |
| metodyka benchmarków | [R23] | wspólne instancje, wiele ziaren i raportowanie rozkładu wyników |
| solver CP-SAT | [R10] | zmienne całkowite, limity czasu, hints i interpretacja statusów |
| profil SAR ICEYE | [R11] | publiczne tryby i parametry produktów; wartości modelowe są oznaczone osobno |
| profil EO Pléiades Neo | [R12] | publiczne parametry produktów optycznych i systemu |
| zachmurzenie EO | [R13] | godzinowa prognoza `cloud_cover` jako jawny wskaźnik warunków |
| walidacja i eksport STK | [R14], [R15], [R24] | raporty Access/AER oraz podstawa przyszłego TLE/OEM exportu |
| geometrie AOI | [R16] | kolejność współrzędnych i struktura GeoJSON |
| przyszłe ML | [R25], [R27] | klasyfikacja wykonalności i GNN pozostają kierunkami dalszych prac |

## Ważne rozróżnienia

- Publiczny rekord OMM jest wejściem do modelu, a nie precyzyjną efemerydą
  operatora.
- Transformacja TEME → ECEF jest uproszczona. Pełny model EOP, precesji,
  nutacji i ruchu bieguna nie został zaimplementowany.
- Graf konfliktów opisuje ograniczenia parowe. Pamięć, czas pracy sensora i
  limity akwizycji pozostają osobnymi ograniczeniami planerów.
- Greedy 2.0 nie jest przepisaniem wzorów PSB/POC. Jest ich adaptacją do
  istniejącego scoringu, okazji SAR/EO i grafu projektu.
- Planer Hybrid nie odtwarza całego solvera Antuoriego i in. Nie implementuje
  pełnego LNS ani ich dokładnego rozkładu na komponenty TSPTW. W wersji 1.3.0
  przekazuje jednak model pamięci i downlinku zarówno do Greedy, jak i lokalnego
  CP-SAT. Zachowuje ogólny schemat: szybki incumbent, ograniczone podproblemy CP
  oraz akceptacja poprawy.
- Profile preferencji są ważoną funkcją użyteczności. Nie są implementacją
  ELECTRE III, TOPSIS ani pełnej analizy przestrzeni wag.
- Parametry ICEYE i Pléiades Neo pochodzą z materiałów publicznych albo są
  oznaczone jako `MODEL_DERIVED`; nie należy ich interpretować jako niepubliczne
  ograniczenia taskingu.
- STK jest zewnętrznym środowiskiem referencyjnym. Zgodność raportów nie oznacza
  zgodności z operacyjnym systemem operatora.

## Bibliografia i dokumentacja

### Orbity, SGP4 i układy odniesienia

**[R1]** Consultative Committee for Space Data Systems, *Orbit Data Messages*,
CCSDS 502.0-B-3, Issue 3, 2023.
<https://ccsds.org/Pubs/502x0b3e1.pdf>

**[R2]** T. S. Kelso, *A New Way to Obtain GP Data (aka TLEs)*, CelesTrak.
<https://celestrak.org/NORAD/documentation/gp-data-formats.php>

**[R3]** D. A. Vallado, P. Crawford, R. Hujsak, T. S. Kelso,
“Revisiting Spacetrack Report #3,” AIAA/AAS Astrodynamics Specialist
Conference, AIAA 2006-6753, 2006.
<https://celestrak.org/publications/AIAA/2006-6753/>

**[R4]** G. Petit, B. Luzum (red.), *IERS Conventions (2010)*,
IERS Technical Note No. 36, 2010.
<https://iers-conventions.obspm.fr/content/tn36.pdf>

**[R5]** National Geospatial-Intelligence Agency,
*Department of Defense World Geodetic System 1984: Its Definition and
Relationships with Local Geodetic Systems*, NGA.STND.0036_1.0.0, 2014.
<https://earth-info.nga.mil/index.php?dir=wgs84&action=wgs84>

### Planowanie akwizycji i optymalizacja

**[R6]** X. Wang, G. Wu, L. Xing, W. Pedrycz,
“Agile Earth Observation Satellite Scheduling Over 20 Years: Formulations,
Methods, and Future Directions,” *IEEE Systems Journal*, 15(3), 3881–3892,
2021. DOI: <https://doi.org/10.1109/JSYST.2020.2997050>

**[R7]** B. Ferrari, J.-F. Cordeau, M. Delorme, M. Iori, R. Orosei,
“Satellite Scheduling Problems: A Survey of Applications in Earth and Outer
Space Observation,” *Computers & Operations Research*, 173, 106875, 2025.
DOI: <https://doi.org/10.1016/j.cor.2024.106875>

**[R8]** E. Bensana, M. Lemaître, G. Verfaillie,
“Earth Observation Satellite Management,” *Constraints*, 4, 293–299, 1999.
DOI: <https://doi.org/10.1023/A:1026488509554>

**[R9]** H. Chen, S. Peng, C. Du, J. Li,
*Earth Observation Satellites: Task Planning and Scheduling*, Springer, 2023.
DOI: <https://doi.org/10.1007/978-981-99-3565-9>

**[R10]** Google, *OR-Tools: CP-SAT Solver* oraz *Setting Solver Limits*.
<https://developers.google.com/optimization/cp/cp_solver>
<https://developers.google.com/optimization/cp/cp_tasks>

**[R17]** D. Eddy, *Task Planning for Earth Observing Satellite Systems*,
rozprawa doktorska, Stanford University, 2021.
<https://purl.stanford.edu/fp397ds6833>

**[R18]** V. Antuori, D. T. Wojtowicz, E. Hebrard,
“Solving the Agile Earth Observation Satellite Scheduling Problem with CP and
Local Search,” w: *31st International Conference on Principles and Practice of
Constraint Programming (CP 2025)*, LIPIcs 340, art. 3, 2025.
DOI: <https://doi.org/10.4230/LIPIcs.CP.2025.3>

**[R19]** R. Xu, H. Chen, X. Liang, H. Wang,
“Priority-Based Constructive Algorithms for Scheduling Agile Earth Observation
Satellites with Total Priority Maximization,” *Expert Systems with
Applications*, 51, 195–206, 2016.
DOI: <https://doi.org/10.1016/j.eswa.2015.12.039>

**[R20]** G. Verfaillie, X. Olive, C. Pralet, S. Rainjonneau, I. Sebbag,
“Planning Acquisitions for an Ocean Global Surveillance Mission,”
*International Workshop on Planning and Scheduling for Space*, 2011/2012.
<https://hal.science/hal-01061393>

**[R21]** A. E. Vasegaard, M. Picard, P. Nielsen, S. Saha,
“A Three-Stage MCDM and Extended Longest Path Algorithm for the Satellite Image
Acquisition Scheduling Problem,” *IEEE Access*, 12, 28169–28185, 2024.
DOI: <https://doi.org/10.1109/ACCESS.2024.3366454>

**[R22]** Consultative Committee for Space Data Systems,
*Mission Planning and Scheduling*, CCSDS 529.0-G-1, Issue 1, 2018.
<https://public.ccsds.org/Pubs/529x0g1.pdf>

**[R23]** A. Globus, J. Crawford, J. Lohn, A. Pryor,
“A Comparison of Techniques for Scheduling Earth Observing Satellites,”
*IAAI 2004*, 836–843, 2004.
DOI: <https://doi.org/10.5555/1597321.1597333>

**[R24]** A. Conda Ramesh,
*Mission Planning and Analyses for Phase C and D of an Earth Observation
Mission*, praca magisterska, Politecnico di Milano, 2023.

**[R25]** R. Barrault, C. Pralet, G. Picard, E. Sawyer, A. Chan-Hon-Tong,
“Learning the Feasibility of Sets of Acquisition Tasks for Earth Observation
Satellites,” IWPSS 2025, HAL hal-05099261, 2025.
<https://hal.science/hal-05099261>

**[R26]** D. Eddy, M. J. Kochenderfer,
“A Maximum Independent Set Method for Scheduling Earth-Observing Satellite
Constellations,” *Journal of Spacecraft and Rockets*, 58(5), 1416–1429, 2021.
<https://arxiv.org/abs/2008.08446>

**[R27]** A. Jacquet, G. Infantes, N. Meuleau, E. Benazera, S. Roussel,
V. Baudoui, J. Guerra, “Earth Observation Satellite Scheduling with Graph
Neural Networks,” *17th European Workshop on Reinforcement Learning*, 2024.
<https://arxiv.org/abs/2408.15041>

**[R28]** A. J. Vázquez Álvarez, R. S. Erwin,
*An Introduction to Optimal Satellite Range Scheduling*, Springer, 2015.
DOI: <https://doi.org/10.1007/978-3-319-25498-3>

### Systemy obrazowania i publiczne źródła danych

**[R11]** ICEYE, *SAR Product Documentation*.
<https://sar.iceye.com/>

**[R12]** Airbus Defence and Space, *Pléiades Neo User Guide* i centrum
materiałów technicznych.
<https://space-solutions.airbus.com/contact-us/pleiades-neo-user-guide/>
<https://space-solutions.airbus.com/resource-center/>

**[R13]** Open-Meteo, *Weather Forecast API Documentation*.
<https://open-meteo.com/en/docs>

### Walidacja i formaty geometrii

**[R14]** Ansys, *Systems Tool Kit (STK) Help*.
<https://help.agi.com/stk/>

**[R15]** Ansys, *STK Access AER Data Provider*.
<https://help.agi.com/stk/Subsystems/dataProviders/Content/html/dataProviders/Access_AER_Data.htm>

**[R16]** H. Butler i in., *The GeoJSON Format*, RFC 7946, 2016.
<https://www.rfc-editor.org/rfc/rfc7946>

## Repozytoria referencyjne

Data dostępu do repozytoriów: **22 lipca 2026 r.**

**[G1]** `Mala1180/satellites-optimization-algorithms` — model DTO, pamięci,
downlinku oraz ILP/GA. Licencja GPL-3.0.
<https://github.com/Mala1180/satellites-optimization-algorithms>

**[G2]** `AlexVasegaard/EOS` — generator scenariuszy, pogoda, MCDM, solvery i
wizualizacja. Licencja MIT.
<https://github.com/AlexVasegaard/EOS>

**[G3]** `AlexVasegaard/EOSS_GECCO25` — instancja benchmarkowa i reprezentacja
konfliktów dla problemu EOSS.
<https://github.com/AlexVasegaard/EOSS_GECCO25>

**[G4]** `Issam-KEBIRI/Optimization-of-the-satellite-image-acquisition-plan` —
mały model OPL/CPLEX z wariantem niezawodności instrumentów. Licencja MIT.
<https://github.com/Issam-KEBIRI/Optimization-of-the-satellite-image-acquisition-plan>

**[G5]** `carlosfab/satellite_scheduling_ga` — algorytm genetyczny dla
harmonogramowania satelitarnego. Licencja GPL-3.0.
<https://github.com/carlosfab/satellite_scheduling_ga>

## Cytowanie projektu

Przy opisie wyników należy oddzielnie cytować:

- Satellite Acquisition Planner jako oprogramowanie — nazwa, wersja, tag lub
  commit, adres repozytorium i data dostępu;
- publikacje odpowiadające analizowanej metodzie, np. [R17] i [R26] dla grafu,
  [R19] dla Greedy 2.0, [R18] dla Hybrid oraz [R21] dla profili preferencji;
- standard lub dokumentację danych, np. [R1]–[R3] dla OMM/SGP4;
- epokę snapshotu OMM, źródło pogody i pełną konfigurację eksperymentu.
