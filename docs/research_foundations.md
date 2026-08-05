# Podstawy badawcze projektu

Ten dokument wskazuje, które elementy Satellite Acquisition Planner są
adaptacją koncepcji opisanych w literaturze, które są rozwiązaniami własnymi,
a które pozostają jedynie kierunkiem dalszych prac. Celem jest umożliwienie
rzetelnego opisu projektu jako pracy studenckiej opartej na istniejącym dorobku,
bez sugerowania skopiowania kodu lub pełnego odtworzenia cudzego algorytmu.

## Klasyfikacja modelu

W terminologii przeglądu Wang i in. [R6] program realizuje dyskretny,
wielosatelitarny wariant problemu AEOSSP. Zmienna decyzyjna odpowiada
konkretnej okazji akwizycyjnej, a model uwzględnia okna czasowe, przejścia
między orientacjami, ograniczenia zasobów, priorytety i heterogeniczne sensory.
Planowanie statyczne jest rozszerzone o reaktywne przeplanowanie.

Bieżąca implementacja łączy cztery poziomy rozwiązania:

1. **model oparty na okazjach (`opportunity-based`)** — jedna jawna okazja jest
   jednym kandydatem do wyboru;
2. **heurystykę konstrukcyjną** — szybki plan początkowy Greedy 2.0;
3. **lokalną poprawę dokładną** — CP-SAT optymalizuje ograniczone sąsiedztwa,
   zachowując plan Greedy jako rozwiązanie bazowe (`incumbent`);
4. **zintegrowane zasoby danych** — akwizycje, pamięć i downlink są liczone
   na wspólnej osi czasu.

## Mapa źródło → implementacja

| Element projektu | Podstawa | Zakres rzeczywistej adaptacji |
|---|---|---|
| dyskretne okazje akwizycyjne | Eddy [R17], Wang i in. [R6] | każda wykonalna okazja jest osobnym kandydatem binarnym |
| graf niewykonalności | Eddy [R17], EOSS_GECCO25 [G3] | parowe konflikty tego samego zlecenia, par SAR–EO i przejść satelity |
| Greedy 2.0 | Xu i in. [R19] | rzadkość okien, koszt zasobów i koszt blokowanych okazji; nie jest to kopia PSB/POC 1:1 |
| Hybrid | Antuori i in. [R18] | Greedy jako rozwiązanie bazowe, lokalne podproblemy CP-SAT, iteracyjna akceptacja poprawy |
| profile decyzyjne | Vasegaard/EOS [G2] i literatura MCDM [R21] | jawne profile wag; bez pełnego ELECTRE III i TOPSIS |
| reaktywne przeplanowanie | Verfaillie i in. [R20], CCSDS [R22] | zachowanie operacji wykonanych i zamrożonych oraz ponowne rozwiązanie części planu |
| porównania algorytmów | Globus i in. [R23] | wspólne instancje, ziarna, wiele powtórzeń i raportowanie rozkładu wyników |
| publiczne orbity i OEM/TLE | Ramesh [R24], Vallado i in. [R3] | OMM/TLE, SGP4 i dokumentacja przyszłego eksportu OEM/STK |
| dynamiczna pamięć i downlink | Antuori i in. [R18], CCSDS [R22], Vázquez Álvarez i Erwin [R28] | stacje, kontakty, przepustowość, pamięć na osi czasu i pełna dostawa jako opcja |

## Graf niewykonalności okazji

Moduł `app/planning/conflict_graph.py` buduje nieskierowany graf

$$
G=(V,E),
$$

gdzie `V` jest zbiorem wykonalnych okazji, a krawędź `(i,j)` oznacza, że obie
okazje nie mogą należeć jednocześnie do harmonogramu. W bieżącej implementacji
rejestrowane są trzy przyczyny:

- `SAME_REQUEST_ALTERNATIVE` — konkurujące alternatywy jednego zlecenia;
- `DUAL_PAIR_INCOMPATIBLE` — niezgodna para SAR–EO;
- `SATELLITE_TRANSITION` — brak czasu na wykonanie obu operacji z wymaganym
  przeorientowaniem i stabilizacją.

Graf jest odpowiednikiem perspektywy niewykonalności opisanej przez Eddy’ego
[R17]. Nie wszystkie ograniczenia są parowe. Pamięć całkowita, czas pracy i
limity akwizycji pozostają w modelach Greedy/CP-SAT i nie są sztucznie
zamieniane na krawędzie.

Interfejs pokazuje liczbę węzłów, krawędzi, gęstość, komponenty spójności,
rozkład przyczyn i najbardziej konfliktowe okazje.

## Greedy 2.0

Klasyczny Greedy pozostaje dostępny dla zgodności. Po włączeniu heurystyki
badawczej ranking okazji przyjmuje postać:

$$
H_i = U_i + \frac{w_s}{n_i}
      - w_d \tau_i
      - w_m D_i
      - w_c \overline{U_i^{\mathrm{blocked}}}\ln(1+|B_i|),
$$

gdzie:

$$
B_i = \{\mathrm{req}(j) \mid j\in N_i,\; \mathrm{req}(j)\neq\mathrm{req}(i)\},
$$

oraz

$$
\overline{U_i^{\mathrm{blocked}}}
= \frac{1}{|B_i|}
  \sum_{b\in B_i}
  \max_{\substack{j\in N_i\\\mathrm{req}(j)=b}} U_j.
$$

Dla `B_i=∅` koszt konfliktowy jest równy zero.

Znaczenie symboli:

- `U_i` — wspólna użyteczność okazji;
- `n_i` — liczba alternatywnych okazji danego zlecenia;
- `τ_i` — czas trwania akwizycji;
- `D_i` — objętość danych akwizycji;
- `N_i` — konfliktujące okazje innych zleceń;
- `B_i` — różne zlecenia blokowane przez wybór okazji;
- `w_s`, `w_d`, `w_m`, `w_c` — jawne wagi profilu.

Implementacja najpierw wybiera największą użyteczność konfliktującej okazji dla
każdego blokowanego zlecenia, a następnie oblicza średnią z tych wartości.
Zlecenia z mniejszą liczbą alternatyw są rozpatrywane wcześniej. Konstrukcja
jest inspirowana rozdzieleniem korzyści i kosztu utraconych możliwości w PSB
i POC Xu i in. [R19], ale została przystosowana do istniejącej funkcji celu,
par SAR–EO i grafu konfliktów projektu.

## Planer Hybrid

Moduł `app/planning/hybrid.py` realizuje następującą procedurę:

```text
Greedy 2.0 → rozwiązanie bazowe
      ↓
budowa grafu konfliktów
      ↓
wybór sąsiedztwa zleceń
      ↓
zablokowanie decyzji poza sąsiedztwem
      ↓
CP-SAT z podpowiedzią rozwiązania bazowego
      ↓
akceptacja wyłącznie poprawy
```

Dla każdej iteracji CP-SAT może zmienić wybory tylko dla ograniczonej grupy
zleceń powiązanych konfliktami. Pozostałe decyzje są ustalane zgodnie z
aktualnym rozwiązaniem bazowym. Rozwiązanie kandydujące jest odrzucane, gdy
pogarsza wykonalność. Poprawa statusu, na przykład przejście z `INFEASIBLE` do
`FEASIBLE`, ma pierwszeństwo. Przy równym statusie kandydat musi zwiększyć
funkcję celu o co najmniej skonfigurowany próg.

Jeżeli rozwiązanie początkowe Greedy 2.0 jest wykonalne, wynika z tego własność:

$$
F_{\mathrm{Hybrid}} \geq F_{\mathrm{Greedy\,2.0}}.
$$

Nie jest to dowód optymalności globalnej. Jest to zachowanie najlepszego
znanego rozwiązania początkowego przy tej samej klasie wykonalności. Podejście
jest autorską adaptacją schematu Greedy–CP–Local Search Antuoriego, Wojtowicza
i Hebrarda [R18]. Ich solver rozwiązuje inne podproblemy; projekt adaptuje
również ideę zintegrowanego planowania pamięci i downlinku.

## Profile preferencji

`app/planning/profiles.py` udostępnia:

- `BALANCED`,
- `EMERGENCY`,
- `QUALITY_FIRST`,
- `THROUGHPUT`,
- `SAR_EO_FUSION`,
- `CUSTOM`.

Profile jawnie ustawiają wagi priorytetu, jakości, pokrycia, obowiązkowości,
kompletności SAR–EO oraz kosztów heurystycznych. Są uproszczoną warstwą MCDM
inspirowaną systemem EOS [G2] i pracą Vasegaarda i in. [R21]. Nie należy ich
nazywać implementacją ELECTRE III: obecna wersja wykorzystuje ważoną funkcję
użyteczności, bez progów obojętności, preferencji i weta.

## Dynamiczna pamięć i downlink

Model zasobów danych obejmuje jawne stacje naziemne, okna kontaktu i ilość danych
przesyłaną w każdym oknie. Pamięć jest liczona na osi zdarzeń, a nie jako
wyłącznie sumaryczny budżet dobowy. Model CP-SAT łączy binarne decyzje
akwizycji z całkowitą ilością danych wysyłaną w kontaktach. Greedy stosuje
deterministyczny przydział chronologiczny i walidację całego profilu pamięci.

Jest to autorska adaptacja zintegrowanego planowania obserwacji, pamięci i
transmisji opisanego przez Antuoriego i in. [R18]. Nazwy domenowe oraz cykl
planowania są zgodne z pojęciami CCSDS Mission Planning and Scheduling [R22],
a ograniczenia kontaktów są powiązane z literaturą Satellite Range Scheduling
[R28]. Scenariusze demonstracyjne używają danych syntetycznych.

## Co pozostaje autorskie

Literatura uzasadnia strukturę problemu i wybrane metody, lecz następujące
połączenie jest specyficzne dla Satellite Acquisition Planner:

- wspólny model SAR i EO;
- tryby `SINGLE`, `DUAL_OPTIONAL` i `DUAL_REQUIRED`;
- zgodność par SAR–EO z limitem separacji;
- połączenie pogody EO z publicznym OMM/SGP4;
- integracja planowania, przeplanowania, raportów, archiwów projektu,
  śledzenia i walidacji STK;
- sposób zdefiniowania profili demonstracyjnych ICEYE i Pléiades Neo.

## Repozytoria referencyjne i licencje

Kod projektu został napisany w obrębie tego projektu. Nie skopiowano kodu
z analizowanych repozytoriów.

| Repozytorium | Wykorzystana koncepcja | Stan licencji i decyzja |
|---|---|---|
| `Mala1180/satellites-optimization-algorithms` [G1] | DTO, pamięć i downlink jako koncepcja porównawcza | GPL-3.0 — brak kopiowania kodu |
| `AlexVasegaard/EOS` [G2] | przepływ end-to-end, MCDM, ELPA | MIT — wykorzystano koncepcje i cytowanie, bez kopiowania modułów |
| `AlexVasegaard/EOSS_GECCO25` [G3] | macierz/graf niewykonalności i duże benchmarki | opis konkursu; brak kodu do przejęcia w tej wersji |
| `Issam-KEBIRI/Optimization-of-the-satellite-image-acquisition-plan` [G4] | niezawodność instrumentów jako przyszłe rozszerzenie | MIT — brak kopiowania modelu OPL |
| `carlosfab/satellite_scheduling_ga` [G5] | GA jako przyszły algorytm porównawczy | GPL-3.0 — brak kopiowania kodu |

## Czego bieżąca implementacja nie obejmuje

- pełnego LNS z wieloma operatorami destroy/repair;
- energii, temperatury i cyklu pracy instrumentu;
- algorytmu genetycznego, simulated annealing, GNN lub DRL;
- klasyfikatora wykonalności z pracy Barraulta i in. [R25];
- pełnego ELECTRE III, TOPSIS lub frontu Pareto;
- solvera MIS/ReduMIS z pracy Eddy’ego;
- eksportu kompletnego scenariusza STK/OEM.

Te elementy pozostają opisanymi kierunkami rozwoju, a nie deklarowanymi
funkcjami bieżącego wydania.

## Zalecany zapis w pracy lub prezentacji

> Satellite Acquisition Planner jest autorską implementacją problemu
> planowania akwizycji opartego na okazjach (`opportunity-based`) dla
> heterogenicznej konstelacji SAR/EO. Model grafu niewykonalności oparto na
> interpretacji grafowej Eddy’ego, heurystykę Greedy 2.0 na koncepcjach korzyści
> i kosztu utraconych możliwości Xu i in., a procedurę Hybrid na schemacie
> Greedy–CP–Local Search opisanym przez Antuoriego, Wojtowicza i Hebrarda.
> Warstwa profili decyzyjnych jest uproszczoną adaptacją podejścia
> wielokryterialnego Vasegaarda i in. Dynamiczna pamięć i downlink adaptują
> zintegrowany model zasobów Antuoriego i in. oraz pojęcia CCSDS. Rozwiązania
> zostały ponownie zaimplementowane i rozszerzone o własny model SAR–EO,
> pogodę, przeplanowanie oraz integrację orbitalną.
