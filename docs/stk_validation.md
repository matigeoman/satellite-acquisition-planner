# Walidacja okien dostępu względem STK

Moduł **Walidacja STK** porównuje okna wyznaczone przez publiczny model
`CelesTrak OMM + SGP4 + publiczny profil sensora` z raportami wygenerowanymi
w Systems Tool Kit. Definicje raportów i dostawcy danych są opisane
w dokumentacji Ansys [R14], [R15] z
[bibliografii projektu](references.md).

## Przebieg

1. W module **Okna dostępu** wyznacz okna dla zlecenia.
2. W module **Walidacja STK** wybierz parę satelita–tryb.
3. Pobierz ZIP przypadku walidacyjnego.
4. Odtwórz w STK scenariusz, satelitę, cel i ograniczenia sensora.
5. Wyeksportuj raport Access do CSV.
6. Opcjonalnie wyeksportuj raport AER.
7. Zaimportuj raporty do aplikacji i pobierz wyniki porównania.

## Obsługiwany raport Access

Parser rozpoznaje przecinek, średnik lub tabulator oraz typowe kolumny:

- `Access Number`,
- `Start Time (UTCG)`,
- `Stop Time (UTCG)`,
- `Duration (sec)`.

Wyliczane są błędy początku, końca i długości okna, udział nakładania oraz
okna niedopasowane.

## Obsługiwany raport AER

Wymagane kolumny:

- `Time (UTCG)`,
- `Azimuth (deg)`,
- `Elevation (deg)`,
- `Range (km)`.

Próbki STK są dopasowywane do najbliższej próbki dyskretnej propagacji.
Dla poligonu porównanie AER odnosi się do centroidu AOI.

## Interpretacja

Walidacja nie oznacza odtworzenia operacyjnego planu operatora. Publiczne OMM
nie są precyzyjnymi efemerydami, a model sensora nie zawiera wszystkich
niejawnych ograniczeń termicznych, energetycznych i manewrowych. Wyniki służą
do oceny dokładności jawnego modelu akademickiego.
