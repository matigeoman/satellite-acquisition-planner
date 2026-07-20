# Śledzenie satelitów na żywo i mapa nieba

Moduł **Śledzenie satelitów na żywo** prezentuje pozycje obiektów orbitalnych
propagowane z publicznych elementów GP/OMM przez SGP4. Nie jest to telemetria
pokładowa ani potwierdzenie stanu operatora satelity.

## Zakres funkcjonalny

Moduł udostępnia cztery widoki:

1. **Mapa nieba** — lokalny układ azymut–elewacja z aktualnymi pozycjami i
   przewidywaną trajektorią przez kolejne 45 minut.
2. **Mapa Ziemi** — aktualne podpunkty satelitów, 90-minutowe ground tracki,
   pozycję obserwatora, terminator dnia i nocy oraz referencyjny footprint.
3. **Najbliższe przeloty** — predykcje AOS, maksimum elewacji i LOS dla
   wybranego progu elewacji.
4. **Kontekst planera** — okna dostępu oraz zaplanowane akwizycje dla
   wyróżnionego satelity.

## Źródła danych

Moduł korzysta z snapshotu OMM znajdującego się w stanie aplikacji. Snapshot
może pochodzić z:

- bieżącego pobrania CelesTrak,
- lokalnego cache,
- scenariusza `POLAND_DEMO` działającego bez sieci.

W interfejsie wyświetlany jest wiek elementów orbitalnych oraz heurystyczna
klasa jakości:

- do 24 h — świeże,
- do 72 h — akceptowalne,
- do 7 dni — stare,
- powyżej 7 dni — bardzo stare.

Klasa jest informacją operatorską, a nie formalnym oszacowaniem błędu pozycji.

## Układ topocentryczny

Pozycja propagowana jest przeliczana do układu ECEF, a następnie do lokalnego
układu ENU obserwatora. Z wektora ENU wyznaczane są:

- azymut,
- elewacja,
- odległość skośna,
- przybliżona prędkość radialna.

## Predykcja przelotów

Dla każdego satelity wykonywana jest propagacja dyskretna. Przelot jest ciągłym
przedziałem, w którym elewacja pozostaje powyżej ustawionego progu. Przecięcia
progu dla AOS i LOS są interpolowane liniowo pomiędzy próbkami. Maksimum jest
wybierane z próbek w obrębie przelotu.

Domyślne ustawienia:

- prognoza: 24 h,
- krok predykcji: 30 s,
- próg elewacji: 5°,
- mapa nieba: 45 min do przodu,
- ground track: 45 min wstecz i 45 min do przodu.

## Widoczność optyczna

Ocena widoczności łączy:

- położenie satelity nad lokalnym horyzontem,
- uproszczony cylindryczny model cienia Ziemi,
- elewację Słońca nad obserwatorem.

Status jest klasyfikowany jako:

- widoczny optycznie,
- pod horyzontem,
- satelita w cieniu Ziemi,
- niebo zbyt jasne.

Jest to estymacja demonstracyjna. Nie uwzględnia jasności satelity, atmosfery,
przeszkód terenowych, zachmurzenia lokalnego ani charakterystyki optycznej
obserwatora.

## Sterowanie czasem

Dostępne są dwa tryby:

- **Na żywo** — czas UTC jest odświeżany co 2 sekundy,
- **Symulacja** — wybrana data i godzina mogą być odtwarzane z prędkością
  `1×`, `10×` lub `60×`.

Automatyczne odświeżanie obejmuje wyłącznie fragment strony, dzięki czemu nie
przeładowuje całej aplikacji.

## Referencyjny footprint

Footprint na mapie Ziemi jest okręgiem o promieniu ustawionym przez użytkownika.
Służy do wizualizacji i nie zastępuje geometrii konkretnego sensora, trybu
obrazowania, off-nadir ani rzeczywistego swathu.

## Dane demonstracyjne

Plik:

```text
examples/poland_demo/live_tracking_reference.json
```

zawiera referencyjny stan sześciu satelitów i predykcję przelotów nad WAT dla
24-godzinnego przedziału scenariusza demonstracyjnego.

## Walidacja wydania

Polecenie:

```powershell
python -m app.cli release-check --algorithm BOTH --cp-sat-time-limit 2
```

sprawdza dodatkowo:

- propagację bieżących stanów dla sześciu obiektów,
- dodatnią odległość topocentryczną,
- występowanie przelotów AOS/MAX/LOS w ciągu 24 godzin.
