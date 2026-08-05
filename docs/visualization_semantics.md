# Semantyka i ograniczenia wizualizacji

Dokument określa, co przedstawiają grafiki Satellite Acquisition Planner oraz
jak należy je opisywać w raportach, prezentacjach i pracy dyplomowej. Jego celem
jest oddzielenie wyników obliczeniowych od elementów poglądowych.

## Zasady ogólne

Każda istotna wizualizacja powinna umożliwiać rozpoznanie:

1. źródła danych;
2. chwili lub przedziału czasu w UTC;
3. układu odniesienia lub rodzaju projekcji;
4. jednostek;
5. charakteru grafiki: wynik obliczeń, aproksymacja albo schemat poglądowy.

Elementu poglądowego nie należy przedstawiać jako pomiaru, telemetrii,
precyzyjnej efemerydy operatora ani wyniku modelu, którego aplikacja nie
implementuje.

## Globus operacyjny

### Ślad naziemny

Ślad naziemny jest rzutem propagowanych stanów OMM/SGP4 na powierzchnię Ziemi.
Współrzędne geograficzne są wyznaczane w modelu związanym z Ziemią, z użyciem
zaimplementowanej transformacji oraz publicznych danych EOP, jeśli są dostępne.

Poprawne określenia:

- ślad naziemny;
- propagowana pozycja podsatellitarna;
- trajektoria względem obracającej się Ziemi.

Nie należy nazywać śladu naziemnego orbitą inercjalną.

### Widok przestrzenny 3D

Krzywa 3D na globusie jest budowana z szerokości geograficznej, długości
geograficznej i wysokości propagowanego stanu. Przedstawia więc przestrzenną
trajektorię w układzie związanym z obracającą się Ziemią.

Nie jest to bezpośredni wykres wektora położenia TEME w nieruchomym układzie
inercjalnym. W interfejsie i pracy zalecane są określenia:

- przestrzenna trajektoria względem Ziemi;
- trajektoria 3D w układzie związanym z Ziemią;
- propagowana pozycja nad modelem Ziemi.

Określenie „orbita 3D” powinno być uzupełnione informacją o układzie związanym
z Ziemią, aby nie sugerowało wizualizacji inercjalnej.

### Znaczniki satelitów

Znacznik reprezentuje punktową pozycję satelity dla wybranej chwili. Wielkość,
kolor i symbol znacznika służą identyfikacji i wyróżnieniu obiektu. Nie
przedstawiają rzeczywistych wymiarów ani orientacji bryły.

Aplikacja nie wyznacza:

- orientacji attitude;
- kątów yaw, pitch i roll;
- stanu AOCS;
- orientacji paneli słonecznych;
- rzeczywistego ustawienia anteny;
- kierunku osi optycznej wynikającego z telemetrii operatora.

Dlatego ikony i znaczniki nie mogą być interpretowane jako rzeczywista
orientacja statku kosmicznego.

## Mapa nieba

Mapa nieba używa lokalnego układu topocentrycznego azymut–elewacja:

- azymut 0° oznacza północ;
- azymut rośnie zgodnie z ruchem wskazówek zegara;
- 90° oznacza wschód;
- 180° oznacza południe;
- 270° oznacza zachód;
- środek wykresu oznacza zenit, czyli elewację 90°;
- zewnętrzny okrąg oznacza horyzont, czyli elewację 0°.

Promień wykresu jest równy `90° − elewacja`. Taka konwencja jest zgodna z
lokalną mapą nieba obserwatora i nie przedstawia orientacji bryły satelity.

## Referencyjny footprint

Zielony okrąg w module śledzenia jest geometrycznym okręgiem o promieniu
ustawionym przez użytkownika. Jest to warstwa prezentacyjna do oceny skali i
położenia, a nie rzeczywisty footprint konkretnego trybu obrazowania.

Nie wynika bezpośrednio z:

- pola widzenia sensora;
- kąta off-nadir;
- geometrii stripmap/spotlight;
- szerokości swathu operatora;
- bieżącej orientacji satelity;
- modelu taskingu ICEYE albo Pléiades Neo.

W interfejsie i raportach należy używać określeń:

- referencyjny okrąg pokrycia;
- promień referencyjny;
- poglądowy obszar pokrycia.

Nie należy używać samego określenia „rzeczywisty footprint sensora”, dopóki
warstwa nie zostanie powiązana z konkretnym sensorem, trybem, kątem obserwacji
i modelem orientacji.

## Okna dostępu i planowane akwizycje

Warstwy okien dostępu i planowanych akwizycji wynikają z danych domenowych
aplikacji. Odcinek śladu lub połączenie satelita–AOI oznacza czasową relację
wyznaczoną przez model planera. Nie stanowi potwierdzenia przyjęcia taskingu
przez operatora ani realizacji zobrazowania.

## Fazowanie konstelacji

W obecnej implementacji nie ma osobnego modelu wizualizacji fazowania
konstelacji w znaczeniu konfiguracji Walker, różnic anomalii średniej albo
kontrolowanego odstępu fazowego w jednej płaszczyźnie orbitalnej.

Rozmieszczenie znaczników na globusie wynika z propagowanych publicznych
rekordów OMM. Może ilustrować chwilowe rozmieszczenie obiektów, ale nie powinno
być podpisywane jako zaprojektowane fazowanie konstelacji bez dodatkowego
obliczenia i jawnej definicji miary fazy.

Poprawne określenie obecnej grafiki:

- chwilowe rozmieszczenie propagowanych obiektów;
- pozycje konstelacji dla chwili UTC;
- względne rozmieszczenie na podstawie OMM/SGP4.

## Wykresy raportowe

Wykresy raportowe są budowane z tabel snapshotu raportowego. Należy zachować:

- jawne jednostki osi;
- nazwę agregacji, np. średnia;
- liczbę próbek `n` przy walidacji;
- informację, że funkcja celu jest wielkością modelową, a nie jednostką
  fizyczną;
- rozróżnienie czasu solvera od czasu ściennego.

## Podstawa naukowa

Interpretacja propagacji, układów odniesienia, OMM/SGP4 i walidacji powinna być
czytana łącznie z [`references.md`](references.md) oraz
[`research_foundations.md`](research_foundations.md), w szczególności ze
źródłami CCSDS, Vallado, IERS, WGS 84 i dokumentacją STK.

Publiczne materiały operatorów mogą służyć do opisu jawnych parametrów
produktów i trybów. Nie stanowią podstawy do odtwarzania niepublicznej
orientacji, telemetrii, ograniczeń taskingu ani rzeczywistego footprintu dla
konkretnego zlecenia.
