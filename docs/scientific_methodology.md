# Metodyka naukowa

## Kontekst badawczy

Metodyka wynika z literatury dotyczącej problemów planowania obserwacji
satelitarnych, w której porównuje się metody dokładne, heurystyczne i hybrydowe
przy wspólnych instancjach i ograniczeniach [R6]–[R9]. Projekt nie odtwarza
eksperymentu z jednej publikacji. Definicje scenariuszy, funkcja celu i profile
zakłóceń są jawnie opisanymi elementami autorskimi. Pełne źródła:
[bibliografia projektu](references.md).

## Pytanie badawcze

W jakim stopniu model CP-SAT poprawia jakość planu akwizycji heterogenicznej
konstelacji SAR/EO względem algorytmu zachłannego oraz jaki jest koszt czasowy
tej poprawy?

## Jednostka eksperymentalna

Jednym przebiegiem jest para: scenariusz danych + konfiguracja ograniczeń +
algorytm + limit czasu + random seed.

## Zmienne niezależne

- liczba zleceń,
- gęstość okazji,
- udział zleceń `DUAL_REQUIRED`,
- limit SAR–EO,
- ograniczenia pamięci i czasu pracy,
- zachmurzenie EO,
- limit czasu CP-SAT.

## Zmienne zależne

- funkcja celu,
- realizacja zleceń,
- czas obliczeń,
- liczba akwizycji,
- stabilność po przeplanowaniu,
- błędy względem STK.

## Kontrola eksperymentu

- stałe snapshoty OMM i pogody,
- jawne random seed,
- jedna wersja aplikacji,
- identyczna funkcja celu,
- zapisana konfiguracja solvera,
- eksport surowych danych bez ręcznego przepisywania.

## Walidacja

Walidacja wewnętrzna obejmuje testy modeli i ograniczeń. Walidacja zewnętrzna
porównuje Access/AER z STK. Różnice należy raportować jako MAE, RMSE, błąd ze
znakiem, maksimum oraz stopień nakładania przedziałów.

## Raportowanie źródeł i założeń

Każdy raport naukowy powinien podawać wersję aplikacji, snapshot OMM z epoką,
źródło prognozy pogody, konfigurację solvera i random seed. Parametry oznaczone
jako `MODEL_DERIVED` należy przedstawiać jako założenia modelu, a nie dane
operatora. W części bibliograficznej należy wskazać co najmniej [R3] dla SGP4,
[R6]–[R10] dla planowania oraz [R11]–[R13] dla profili i danych publicznych.
