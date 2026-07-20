# Ograniczenia operacyjne sensorów

Moduł planowania obsługuje dwa poziomy modelu przejścia pomiędzy kolejnymi
akwizycjami tego samego satelity:

- model statyczny, zachowujący kompatybilność z wcześniejszymi scenariuszami,
- model dynamiczny używany domyślnie w zakładce **Planowanie na danych publicznych**.

## Pléiades Neo

Dla sensora EO czas zwrotu jest interpolowany liniowo pomiędzy publicznymi
punktami odniesienia:

| Zmiana kierunku obserwacji | Czas zwrotu |
|---:|---:|
| 10° | 7 s |
| 30° | 12 s |
| 60° | 20 s |

Odległość kątowa jest liczona na podstawie podpisanego kąta off-nadir:
`LEFT < 0`, `RIGHT > 0`, a nadir ma wartość `0`. Do czasu zwrotu dodawany jest
konfigurowalny czas stabilizacji EO. Dla kątów powyżej 60° model wykonuje
liniową ekstrapolację na podstawie ostatniego przedziału.

Warunek kolejności dwóch akwizycji ma postać:

```text
koniec A + czas_przejścia(A → B) ≤ początek B
```

## ICEYE

Dla sensora SAR czas przejścia jest sumą modelowanych składników:

```text
|kąt_B - kąt_A| / prędkość_zwrotu
+ stabilizacja_SAR
+ kara_LEFT_RIGHT
+ kara_zmiany_kategorii_trybu
```

Kara `LEFT/RIGHT` jest dodawana przy zmianie strony obserwacji. Kara zmiany
trybu jest dodawana, gdy kolejne akwizycje należą do różnych kategorii trybu
SAR. Planner może również ograniczyć liczbę akwizycji w jednym modelowanym
przelocie ICEYE. Przeloty są rozdzielane konfigurowalną przerwą czasową.

Parametry ICEYE są jawnymi założeniami modelu badawczego. Nie stanowią
potwierdzonych ograniczeń operacyjnych operatora ani danych niepublicznych.

## Zlecenia SAR + EO

Zlecenia `DUAL_REQUIRED` i `DUAL_OPTIONAL` mogą posiadać
`max_dual_separation_s`. Odstęp jest liczony pomiędzy środkami akwizycji:

```text
|midpoint(SAR) - midpoint(EO)| ≤ max_dual_separation_s
```

Dla `DUAL_REQUIRED` wybrana para musi spełniać limit. Dla `DUAL_OPTIONAL`
pojedyncza akwizycja nadal realizuje podstawową część zlecenia, natomiast
druga akwizycja i premia za parę są dopuszczane tylko dla pary zgodnej
czasowo.

## Greedy i CP-SAT

Oba algorytmy korzystają z tego samego modułu `app.planning.operational`:

- Greedy sprawdza kierunkowy czas przejścia przed każdą decyzją,
- CP-SAT tworzy konflikty par akwizycji, które nie mają wystarczającej przerwy,
- oba planery kontrolują limit akwizycji SAR w przelocie,
- oba planery odrzucają niezgodne czasowo pary SAR + EO.

W modelach ogólnych dynamiczne ograniczenia są domyślnie wyłączone, aby
zachować zgodność wcześniejszych scenariuszy i harmonogramów referencyjnych.
W planowaniu publicznym są domyślnie włączone i mogą zostać wyłączone w UI.

## Diagnostyka

Analiza harmonogramu rozpoznaje kod:

```text
DUAL_SEPARATION_LIMIT
```

gdy zlecenie wymagające SAR i EO ma dostępne okazje obu typów, ale żadna para
nie mieści się w zadanym limicie czasu.
