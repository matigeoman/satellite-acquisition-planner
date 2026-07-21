# Podstawy naukowe, inspiracje i źródła

Ten rozdział rozdziela trzy rodzaje podstaw projektu:

1. **standardy i dokumentację implementacyjną** — wykorzystywane bezpośrednio
   przy formatach danych, propagacji, geometrii i obsłudze solvera;
2. **literaturę problemu planowania satelitarnego** — stanowiącą kontekst dla
   modelu decyzyjnego i eksperymentów;
3. **publiczne materiały operatorów i dostawców danych** — wykorzystywane do
   przygotowania jawnych profili demonstracyjnych.

Satellite Acquisition Planner jest implementacją autorską. Nie odtwarza
jednego opublikowanego algorytmu ani operacyjnego systemu konkretnego operatora.
Funkcja celu, sposób agregacji jakości, budżety zasobów i część ograniczeń są
jawnymi założeniami modelu opisanymi w dokumentacji i kodzie.

## Powiązanie źródeł z elementami aplikacji

| Element projektu | Podstawa | Sposób wykorzystania |
|---|---|---|
| OMM/GP | [R1], [R2] | format i interpretacja publicznych elementów orbitalnych |
| propagacja SGP4 | [R3] | model propagacji zgodny z rodziną SGP4/SDP4 |
| układy odniesienia | [R4], [R5] | punkt odniesienia dla WGS 84 i transformacji niebieski–ziemski |
| model planowania | [R6]–[R9] | definicja klasy problemu, typowe ograniczenia i metody porównawcze |
| solver CP-SAT | [R10] | zmienne całkowite, limity czasu i interpretacja statusów solvera |
| profil SAR ICEYE | [R11] | publiczne tryby i parametry produktów; wartości modelowe są oznaczone osobno |
| profil EO Pléiades Neo | [R12] | publiczne parametry produktów optycznych i systemu |
| zachmurzenie EO | [R13] | godzinowa prognoza `cloud_cover` jako jawny wskaźnik warunków |
| walidacja STK | [R14], [R15] | raporty Access oraz próbki azymut–elewacja–odległość |
| geometrie AOI | [R16] | kolejność współrzędnych i struktura GeoJSON |

## Ważne rozróżnienia

- Publiczny rekord OMM jest wejściem do modelu, a nie precyzyjną efemerydą
  operatora.
- Transformacja TEME → ECEF w aplikacji jest uproszczona. IERS Conventions są
  wskazane jako podstawa rozwiązania o wyższej dokładności, lecz pełny model
  EOP, precesji, nutacji i ruchu bieguna nie został zaimplementowany.
- Literatura planowania satelitarnego uzasadnia traktowanie problemu jako
  kombinatorycznego problemu harmonogramowania z oknami czasowymi i
  ograniczeniami zasobów. Konkretna funkcja celu projektu pozostaje autorska.
- Parametry ICEYE i Pléiades Neo pochodzą z materiałów publicznych lub są
  oznaczone w modelu jako `MODEL_DERIVED`. Nie należy ich interpretować jako
  niepublicznych ograniczeń taskingu.
- STK jest zewnętrznym środowiskiem referencyjnym. Zgodność raportów nie oznacza
  zgodności z operacyjnym systemem planowania operatora.

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
*Earth Observation Satellites: Task Planning and Scheduling*, Springer,
2023. DOI: <https://doi.org/10.1007/978-981-99-3565-9>

**[R10]** Google, *OR-Tools: CP-SAT Solver* oraz *Setting Solver Limits*.
<https://developers.google.com/optimization/cp/cp_solver>
<https://developers.google.com/optimization/cp/cp_tasks>

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

## Cytowanie projektu

Przy opisie wyników należy oddzielnie cytować:

- projekt Satellite Acquisition Planner jako oprogramowanie;
- publikacje lub standardy odpowiadające analizowanemu elementowi, np. [R3]
  dla SGP4, [R6]–[R9] dla planowania i [R11]–[R12] dla profili sensorów;
- datę oraz epokę użytego snapshotu OMM i prognozy pogody.

W cytowaniu oprogramowania należy podać nazwę projektu, wersję, identyfikator
commita lub tag wydania, adres repozytorium oraz datę dostępu.
