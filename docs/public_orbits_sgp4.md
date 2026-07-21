# Publiczne orbity GP/OMM i propagacja SGP4

## Zakres etapu

Aplikacja pobiera publiczne elementy orbitalne GP z CelesTrak w formacie OMM
JSON. Format OMM opisuje standard CCSDS 502.0-B-3, a sposób udostępniania GP
przez CelesTrak dokumentują źródła [R1] i [R2] z
[bibliografii projektu](references.md). Dane są pobierane dla:

- czterech publicznie śledzonych obiektów ICEYE,
- Pléiades Neo 3,
- Pléiades Neo 4.

Rekordy są mapowane na sloty planera `SAR-01`–`SAR-04` oraz `EO-01`–`EO-02`.

## Cache i ograniczenie liczby zapytań

CelesTrak aktualizuje dane GP cyklicznie i wymaga ograniczenia częstotliwości
pobierania. Klient zapisuje odpowiedzi w:

```text
data/generated/orbits/
```

Cache jest ważny przez dwie godziny. Ponowne renderowanie Streamlit korzysta
z pliku lokalnego i nie wysyła kolejnego zapytania. Jeśli odświeżenie się nie
powiedzie, aplikacja może użyć starszego cache i wyświetla ostrzeżenie.

## Propagacja

`Sgp4OrbitPropagator` inicjalizuje rekord `Satrec` bezpośrednio z pól OMM
i propaguje pozycję w układzie TEME zgodnie z rodziną modeli opisaną przez
Vallado i in. [R3]. Następnie wykonywany jest uproszczony obrót TEME → ECEF
na podstawie GMST i konwersja ECEF → geodezyjne WGS 84. Dokumenty IERS i NGA
[R4], [R5] stanowią punkt odniesienia dla rozwiązania o większej dokładności.

Wynik obejmuje:

- czas UTC,
- szerokość geograficzną,
- długość geograficzną,
- wysokość nad elipsoidą,
- wektor położenia TEME,
- wektor prędkości TEME.

Transformacja służy obecnie do wizualizacji śladów naziemnych i geometrii
badawczej. Nie implementuje pełnego łańcucha IERS obejmującego EOP, ruch
bieguna, precesję i nutację. Dokładniejsze wyniki są porównywane z STK.

## Interfejs

Zakładka **Orbity i dane OMM** pozwala:

- pobrać lub odświeżyć OMM,
- pracować wyłącznie z lokalnym cache,
- ustawić horyzont propagacji 1–12 godzin,
- wybrać krok 30–300 sekund,
- zobaczyć ślady naziemne na mapie,
- pobrać rekordy i propagację do JSON.

## Ograniczenia interpretacyjne

Publiczne GP/OMM nie są precyzyjnymi efemerydami operatora. Wyniki należy
opisywać jako orientacyjne okna geometryczne oparte na publicznych danych
i modelu SGP4, a nie potwierdzony tasking komercyjny.
