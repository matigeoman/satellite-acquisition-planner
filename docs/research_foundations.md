# Podstawy badawcze wersji 1.2.0

Ten dokument wskazuje, które elementy Satellite Acquisition Planner 1.2.0 są
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

Wersja 1.2.0 łączy trzy poziomy rozwiązania:

1. **model opportunity-based** — jedna jawna okazja jest jednym kandydatem do
   wyboru;
2. **heurystykę konstrukcyjną** — szybki plan początkowy Greedy 2.0;
3. **lokalną poprawę dokładną** — CP-SAT optymalizuje ograniczone sąsiedztwa,
   zachowując plan Greedy jako incumbent.

## Mapa źródło → implementacja

| Element 1.2.0 | Podstawa | Zakres rzeczywistej adaptacji |
|---|---|---|
| dyskretne okazje akwizycyjne | Eddy [R17], Wang i in. [R6] | każda wykonalna okazja jest osobnym kandydatem binarnym |
| graf niewykonalności | Eddy [R17], EOSS_GECCO25 [G3] | parowe konflikty tego samego zlecenia, par SAR–EO i przejść satelity |
| Greedy 2.0 | Xu i in. [R19] | rzadkość okien, koszt zasobów i koszt blokowanych okazji; nie jest to kopia PSB/POC 1:1 |
| Hybrid | Antuori i in. [R18] | Greedy jako incumbent, lokalne podproblemy CP-SAT, iteracyjna akceptacja poprawy |
| profile decyzyjne | Vasegaard/EOS [G2] i literatura MCDM [R21] | jawne profile wag; bez pełnego ELECTRE III i TOPSIS |
| reaktywne przeplanowanie | Verfaillie i in. [R20], CCSDS [R22] | zachowanie operacji wykonanych i zamrożonych oraz ponowne rozwiązanie części planu |
| porównania algorytmów | Globus i in. [R23] | wspólne instancje, ziarna, wiele powtórzeń i raportowanie rozkładu wyników |
| publiczne orbity i OEM/TLE | Ramesh [R24], Vallado i in. [R3] | OMM/TLE, SGP4 i dokumentacja przyszłego eksportu OEM/STK |

## Graf niewykonalności okazji

Moduł `app/planning/conflict_graph.py` buduje nieskierowany graf

\[
G=(V,E),
\]

gdzie `V` jest zbiorem wykonalnych okazji, a krawędź `(i,j)` oznacza, że obie
okazje nie mogą należeć jednocześnie do harmonogramu. W wersji 1.2.0
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

\[
H_i = U_i + \frac{w_s}{n_i}
      - w_d d_i
      - w_m m_i
      - w_c \overline{U(N_i)}\ln(1+r_i),
\]

gdzie:

- `U_i` — wspólna użyteczność okazji;
- `n_i` — liczba alternatywnych okazji danego zlecenia;
- `d_i` — czas akwizycji;
- `m_i` — objętość danych;
- `N_i` — konfliktujące okazje innych zleceń;
- `r_i` — liczba różnych zleceń blokowanych przez wybór okazji;
- `w_s`, `w_d`, `w_m`, `w_c` — jawne wagi profilu.

Zlecenia z mniejszą liczbą alternatyw są rozpatrywane wcześniej. Konstrukcja
jest inspirowana rozdzieleniem korzyści i kosztu utraconych możliwości w PSB
i POC Xu i in. [R19], ale została przystosowana do istniejącej funkcji celu,
par SAR–EO i grafu konfliktów projektu.

## Planer Hybrid

Moduł `app/planning/hybrid.py` realizuje następującą procedurę:

```text
Greedy 2.0 → incumbent
      ↓
budowa grafu konfliktów
      ↓
wybór sąsiedztwa zleceń
      ↓
zablokowanie decyzji poza sąsiedztwem
      ↓
CP-SAT z podpowiedzią rozwiązania incumbent
      ↓
akceptacja wyłącznie poprawy
```

Dla każdej iteracji CP-SAT może zmienić wybory tylko dla ograniczonej grupy
zleceń powiązanych konfliktami. Pozostałe decyzje są ustalane zgodnie z
aktualnym incumbentem. Rozwiązanie kandydujące jest odrzucane, gdy pogarsza
wykonalność. Poprawa statusu, na przykład przejście z `INFEASIBLE` do `FEASIBLE`, ma pierwszeństwo.
Przy równym statusie kandydat musi zwiększyć funkcję celu o co najmniej
skonfigurowany próg.

Jeżeli rozwiązanie początkowe Greedy 2.0 jest wykonalne, wynika z tego własność:

\[
F_{Hybrid} \geq F_{Greedy\ 2.0}.
\]

Nie jest to dowód optymalności globalnej. Jest to zachowanie najlepszego
znanego rozwiązania początkowego przy tej samej klasie wykonalności. Podejście
jest autorską adaptacją schematu Greedy–CP–Local Search Antuoriego, Wojtowicza i Hebrarda [R18]; ich
solver rozwiązuje inne podproblemy i dodatkowo planuje downlink.

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

Kod wersji 1.2.0 został napisany w obrębie tego projektu. Nie skopiowano kodu
z analizowanych repozytoriów.

| Repozytorium | Wykorzystana koncepcja | Stan licencji i decyzja |
|---|---|---|
| `Mala1180/satellites-optimization-algorithms` [G1] | DTO, pamięć i downlink jako przyszłe rozszerzenie | GPL-3.0 — brak kopiowania kodu |
| `AlexVasegaard/EOS` [G2] | przepływ end-to-end, MCDM, ELPA | MIT — wykorzystano koncepcje i cytowanie, bez kopiowania modułów |
| `AlexVasegaard/EOSS_GECCO25` [G3] | macierz/graf niewykonalności i duże benchmarki | opis konkursu; brak kodu do przejęcia w tej wersji |
| `Issam-KEBIRI/Optimization-of-the-satellite-image-acquisition-plan` [G4] | niezawodność instrumentów jako przyszłe rozszerzenie | MIT — brak kopiowania modelu OPL |
| `carlosfab/satellite_scheduling_ga` [G5] | GA jako przyszły algorytm porównawczy | GPL-3.0 — brak kopiowania kodu |

## Czego wersja 1.2.0 nie implementuje

- pełnego LNS z wieloma operatorami destroy/repair;
- dokładnego modelu downlinku i pamięci zmiennej w czasie;
- energii, temperatury i cyklu pracy instrumentu;
- algorytmu genetycznego, simulated annealing, GNN lub DRL;
- klasyfikatora wykonalności z pracy Barraulta i in. [R25];
- pełnego ELECTRE III, TOPSIS lub frontu Pareto;
- solvera MIS/ReduMIS z pracy Eddy’ego;
- eksportu kompletnego scenariusza STK/OEM.

Te elementy pozostają opisanymi kierunkami rozwoju, a nie deklarowanymi
funkcjami bieżącego wydania.

## Zalecany zapis w pracy lub prezentacji

> Satellite Acquisition Planner 1.2.0 jest autorską implementacją
> opportunity-based problemu planowania akwizycji dla heterogenicznej
> konstelacji SAR/EO. Model grafu niewykonalności oparto na interpretacji
> grafowej Eddy’ego, heurystykę Greedy 2.0 na koncepcjach korzyści i kosztu
> utraconych możliwości Xu i in., a procedurę Hybrid na schemacie
> Greedy–CP–Local Search opisanym przez Antuoriego, Wojtowicza i Hebrarda.
> Warstwa profili decyzyjnych jest uproszczoną adaptacją podejścia
> wielokryterialnego Vasegaarda i in. Rozwiązania zostały ponownie
> zaimplementowane i rozszerzone o własny model SAR–EO, pogodę, przeplanowanie
> oraz integrację orbitalną.
