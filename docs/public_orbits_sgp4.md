# Publiczne orbity GP/OMM i propagacja SGP4

## Zakres modułu

Aplikacja pobiera publiczne elementy orbitalne GP z CelesTrak w formacie OMM
JSON. Format OMM opisuje standard CCSDS 502.0-B-3, a sposób udostępniania GP
przez CelesTrak dokumentują źródła [R1] i [R2] z
[bibliografii projektu](references.md). Dane są pobierane dla:

- czterech publicznie śledzonych obiektów ICEYE,
- Pléiades Neo 3,
- Pléiades Neo 4.

Rekordy są mapowane na sloty planera `SAR-01`–`SAR-04` oraz `EO-01`–`EO-02`.
Rozdzielenie nominalnego profilu misji od dynamicznych elementów OMM opisuje
[System satelitarny, parametry i geometria](satellite_system.md).

## Tryby przypisania satelitów

Aplikacja rozdziela **pobieranie OMM** od **przypisania rekordów do slotów**.
Dostępne są dwa jawne tryby:

- `PINNED` — tryb domyślny i reprodukowalny. Każdy slot ma przypisany
  konkretny numer NORAD oraz kontrolny fragment nazwy. Brak obiektu albo
  niezgodność nazwy zatrzymuje budowę snapshotu zamiast cicho podmieniać
  satelitę;
- `LIVE` — tryb eksploracyjny. Dla ICEYE wybierane są użyteczne rekordy o
  najnowszej epoce OMM, natomiast dla Pléiades preferowane są Neo 3 i Neo 4.
  Skład slotów może zmieniać się wraz z odpowiedzią źródła.

Domyślna konfiguracja `PINNED`:

| Slot | Rodzina | NORAD | Oczekiwana nazwa |
|---|---|---:|---|
| `SAR-01` | ICEYE | 68996 | `ICEYE-X82` |
| `SAR-02` | ICEYE | 60539 | `ICEYE-X43` |
| `SAR-03` | ICEYE | 60546 | `ICEYE-X39` |
| `SAR-04` | ICEYE | 60549 | `ICEYE-X40` |
| `EO-01` | Pléiades Neo | 48268 | `PLEIADES NEO 3` |
| `EO-02` | Pléiades Neo | 49070 | `PLEIADES NEO 4` |

Tryb można zmienić w zakładce **Orbity i dane OMM** albo ustawić dla
środowiska procesu/kontenera:

```text
SATPLAN_ORBIT_SELECTION_MODE=PINNED
```

Snapshoty i archiwa projektu zapisują użyty tryb oraz konfigurację pinów,
dzięki czemu wynik można odtworzyć bez zgadywania, które obiekty zajmowały
sloty.

## Cache OMM i kontrola wieku

Klient zapisuje odpowiedzi w:

```text
data/generated/orbits/
```

Cache jest świeży przez dwie godziny. Gdy pobranie nowych danych nie powiedzie
się, aplikacja może użyć starszego pliku, ale tylko do twardego limitu 72 godzin.
Dane starsze są odrzucane, chyba że wywołujący jawnie zezwoli na pracę z
wygasłym cache. Każdy rekord ma status:

- `FRESH` — wiek do 6 godzin,
- `STALE` — powyżej 6 do 24 godzin,
- `DEGRADED` — powyżej 24 do 72 godzin,
- `EXPIRED` — powyżej 72 godzin.

Planowanie z rekordem `EXPIRED` jest domyślnie blokowane.

## Parametry orientacji Ziemi

Transformacja do układu związanego z Ziemią korzysta z publicznego pliku
CelesTrak `EOP-All-v1.1.txt`. Parser interpoluje dla chwili propagacji:

- `UT1-UTC`,
- współrzędne ruchu bieguna `xp` i `yp`,
- status próbki obserwowanej lub predykcyjnej.

Plik jest zapisywany w:

```text
data/generated/eop/
```

Cache EOP ma TTL 12 godzin i twardy limit wieku siedmiu dni. Brak próbki EOP
dla analizowanej chwili powoduje jawne przejście do trybu przybliżonego, a nie
ciche udawanie wyniku ITRF2020.

## Propagacja i transformacja układów

`Sgp4OrbitPropagator` inicjalizuje rekord `Satrec` bezpośrednio z pól OMM i
propaguje położenie oraz prędkość w układzie TEME zgodnie z rodziną modeli
opisaną przez Vallado i in. [R3]. Następnie wykonywany jest łańcuch:

```text
TEME
  → obrót kątem GMST wyznaczonym z UT1
PEF
  → macierz ruchu bieguna xp/yp
ITRF2020 / Earth Fixed
  → konwersja elipsoidalna WGS 84
LLA
```

Wynik obejmuje:

- czas UTC,
- szerokość, długość i wysokość nad elipsoidą WGS 84,
- wektor położenia i prędkości TEME,
- używaną ramę Earth Fixed,
- jakość transformacji: `OBSERVED`, `PREDICTED` albo `FALLBACK`,
- źródło EOP.

Implementacja nie odtwarza pełnego rozwiązania precyzyjnej astrometrii IERS,
ale uwzględnia składniki istotne dla transformacji SGP4 TEME → ITRF:
`UT1-UTC` i ruch bieguna. Regresja numeryczna dla ICEYE-X82 oraz Pléiades Neo 3
została porównana z efemerydami STK 13; próbki referencyjne znajdują się w
`tests/fixtures/stk_validation/`.

## Interfejs

Zakładka **Orbity i dane OMM** pozwala:

- wybrać tryb `PINNED` albo `LIVE`,
- pobrać lub odświeżyć OMM i EOP,
- pracować z lokalnym cache,
- ustawić horyzont propagacji 1–12 godzin,
- wybrać krok 30–300 sekund,
- zobaczyć ślady naziemne na mapie,
- pobrać rekordy i propagację do JSON.

## Ograniczenia interpretacyjne

Publiczne GP/OMM nie są precyzyjnymi efemerydami operatora. Wyniki należy
opisywać jako badawcze okna geometryczne oparte na publicznych danych i SGP4,
a nie potwierdzony tasking komercyjny. EOP poprawia zgodność ramy Earth Fixed,
lecz nie usuwa błędu wynikającego z wieku i jakości samych elementów GP.
