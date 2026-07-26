# Walidacja okien i transformacji względem STK

Moduł **Walidacja STK** porównuje wyniki modelu
`CelesTrak OMM + SGP4 + EOP + publiczny profil sensora` z raportami i
referencyjnymi efemerydami wygenerowanymi w Systems Tool Kit. Definicje
raportów i dostawcy danych są opisane w dokumentacji Ansys [R14], [R15] z
[bibliografii projektu](references.md).

## Warunki porównania

Przypadek jest miarodajny tylko wtedy, gdy STK i aplikacja używają:

- tego samego rekordu OMM/TLE i tej samej epoki,
- propagatora SGP4,
- tego samego przedziału czasu i skali UTCG,
- identycznych współrzędnych AOI oraz minimalnej elewacji,
- zgodnych parametrów sensora,
- tego samego lub równoważnego pliku EOP i ramy ITRF.

## Przebieg walidacji okien

1. W module **Okna dostępu** wyznacz okna dla zlecenia.
2. W module **Walidacja STK** wybierz parę satelita–tryb.
3. Pobierz ZIP przypadku walidacyjnego.
4. Odtwórz w STK scenariusz, satelitę, cel i ograniczenia sensora.
5. Wyeksportuj raport Access do CSV/TXT.
6. Wyeksportuj raport AER, najlepiej z krokiem 1 s dla wybranego przelotu.
7. Zaimportuj raporty do aplikacji i pobierz wyniki porównania.

## Obsługiwany raport Access

Parser rozpoznaje przecinek, średnik lub tabulator oraz typowe kolumny:

- `Access Number`,
- `Start Time (UTCG)`,
- `Stop Time (UTCG)`,
- `Duration (sec)`.

Wyliczane są błędy początku, końca i długości okna, udział nakładania oraz okna
niedopasowane.

## Obsługiwany raport AER

Wymagane kolumny:

- `Time (UTCG)`,
- `Azimuth (deg)`,
- `Elevation (deg)`,
- `Range (km)`.

Raport musi być wygenerowany w kierunku `Place/Target → Satellite`, aby azymut
i elewacja były interpretowane w lokalnej ramie obserwatora naziemnego.
Próbki STK są dopasowywane czasowo do wyników propagacji. Dla poligonu AER
odnosi się do reprezentatywnego punktu AOI, natomiast procent pokrycia jest
liczony z przecięcia pełnej geometrii AOI z nominalnym footprintem.

## Regresja TEME → ITRF2020

Repozytorium zawiera mały, wersjonowany zestaw próbek z STK 13:

```text
tests/fixtures/stk_validation/
├── eop_2026_07_19_20.txt
└── teme_itrf_reference_2026_07_19.csv
```

Zestaw obejmuje ICEYE-X82 i Pléiades Neo 3. Test propagacji ramy:

1. wczytuje próbkę TEME ze STK,
2. interpoluje `UT1-UTC`, `xp` i `yp`,
3. wykonuje transformację TEME → PEF → ITRF,
4. porównuje wynik z referencyjną pozycją ITRF2020.

Tolerancja testu wynosi 2 cm. Jest to test regresyjny implementacji
transformacji, nie deklaracja dokładności publicznej orbity względem stanu
rzeczywistego satelity.

## Interpretacja

Walidacja nie oznacza odtworzenia operacyjnego planu operatora. Publiczne OMM
nie są precyzyjnymi efemerydami, a model sensora nie zawiera wszystkich
niejawnych ograniczeń termicznych, energetycznych i manewrowych. Wyniki służą
do oceny spójności i dokładności jawnego modelu akademickiego.
