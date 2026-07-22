# Metodyka naukowa

## Kontekst badawczy

Projekt porównuje trzy rodziny metod występujące w literaturze AEOSSP:
heurystykę konstrukcyjną, globalny model Constraint Programming oraz metodę
hybrydową wykorzystującą rozwiązanie początkowe i lokalną poprawę [R6], [R18],
[R19]. Model opportunity-based i graf konfliktów wynikają z prac Eddy’ego
[R17], [R26]. Profile preferencji są uproszczoną adaptacją podejścia MCDM
[R21].

Projekt nie odtwarza jednego eksperymentu ani operacyjnego systemu operatora.
Scenariusze SAR/EO, sposób parowania sensorów i integracja orbitalna są
rozwiązaniami własnymi. Szczegółowe rozróżnienie znajduje się w
[`research_foundations.md`](research_foundations.md).

## Pytanie badawcze

Jak jakość i czas obliczeń planu akwizycji heterogenicznej konstelacji SAR/EO
zmieniają się przy zastosowaniu:

1. Greedy 2.0 z kosztem utraconych okazji;
2. globalnego CP-SAT;
3. Hybrid, w którym CP-SAT poprawia lokalne sąsiedztwa planu Greedy?

## Hipotezy robocze

- **H1:** Greedy 2.0 uzyskuje wynik nie gorszy średnio od klasycznego Greedy w
  scenariuszach przeciążonych, zwłaszcza gdy zlecenia mają różną liczbę
  alternatywnych okien.
- **H2:** Hybrid nie zwraca planu o funkcji celu mniejszej od własnego
  incumbenta Greedy 2.0, ponieważ akceptuje wyłącznie poprawy.
- **H3:** globalny CP-SAT może znaleźć rozwiązanie lepsze od Greedy, ale przy
  krótkim limicie czasu może zakończyć ze statusem `FEASIBLE` i wynikiem
  słabszym od szybko uzyskanego planu zachłannego.
- **H4:** wpływ profilu decyzyjnego jest widoczny w strukturze planu, np.
  `EMERGENCY` zwiększa realizację zleceń obowiązkowych, a `QUALITY_FIRST`
  średnią jakość wybranych akwizycji.

## Jednostka eksperymentalna

Jednym przebiegiem jest zestaw:

```text
wersja aplikacji
+ scenariusz i snapshot danych
+ profil decyzyjny
+ konfiguracja ograniczeń
+ algorytm
+ limit czasu
+ random seed
```

## Zmienne niezależne

- liczba zleceń i okazji;
- gęstość grafu konfliktów;
- udział `DUAL_REQUIRED` i `DUAL_OPTIONAL`;
- profil decyzyjny;
- rezerwa pamięci i ograniczenia czasu pracy;
- model przeorientowania;
- zachmurzenie EO;
- limit czasu CP-SAT/Hybrid;
- rozmiar i liczba sąsiedztw Hybrid.

## Zmienne zależne

- funkcja celu;
- liczba i udział zrealizowanych zleceń;
- realizacja zleceń obowiązkowych;
- czas obliczeń;
- liczba akwizycji SAR i EO;
- kompletność par SAR–EO;
- jakość i objętość danych;
- liczba zaakceptowanych ulepszeń Hybrid;
- gęstość i rozmiary komponentów grafu konfliktów;
- stabilność po przeplanowaniu;
- błędy względem STK.

## Kontrola eksperymentu

- stałe snapshoty OMM i pogody;
- identyczne zlecenia i okazje dla wszystkich algorytmów;
- wspólny scoring i profil decyzyjny;
- jawne random seed;
- jeden wątek solvera w benchmarku referencyjnym;
- co najmniej 5 powtórzeń dla wyników statystycznych;
- jedna wersja Pythona, OR-Tools i aplikacji;
- eksport surowych danych bez ręcznego przepisywania.

Dla jednego powtórzenia wszystkie limity czasowe CP-SAT i Hybrid używają tego
samego ziarna scenariusza. Ziarno zmienia się dopiero między powtórzeniami.

## Analiza wyników

Dla każdej konfiguracji należy raportować co najmniej:

- średnią, odchylenie standardowe, medianę, minimum i maksimum;
- liczbę przypadków lepszych, równych i gorszych od Greedy;
- status `OPTIMAL`, `FEASIBLE`, `INFEASIBLE` lub błąd;
- względną poprawę funkcji celu;
- koszt czasowy poprawy;
- parametry sprzętu i środowiska.

Pojedynczy przebieg nie wystarcza do wniosku o przewadze algorytmu
stochastycznego lub limitowanego czasowo. Zasada wielu ziaren jest zgodna z
metodyką porównań algorytmów harmonogramowania [R23].

## Walidacja

Walidacja wewnętrzna obejmuje testy modeli, grafu, ograniczeń i gwarancji
zachowania incumbenta. Walidacja zewnętrzna porównuje Access/AER z STK.
Różnice należy raportować jako MAE, RMSE, błąd ze znakiem, maksimum oraz stopień
nakładania przedziałów.

## Raportowanie źródeł i założeń

Raport powinien podawać wersję aplikacji, commit, snapshot OMM z epoką, źródło
pogody, konfigurację solvera, profil decyzyjny i seed. Parametry
`MODEL_DERIVED` należy przedstawiać jako założenia modelu, a nie dane operatora.
Cytowania metod należy dobierać do faktycznie analizowanego modułu: [R17],
[R26] dla grafu, [R19] dla Greedy 2.0, [R18] dla Hybrid i [R21] dla profili.
