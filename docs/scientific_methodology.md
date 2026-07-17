# Metodyka naukowa

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
