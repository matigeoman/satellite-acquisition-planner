# Globus 3D Cesium

Moduł `Globus 3D` wizualizuje w jednej animowanej scenie:

- propagowane pozycje ICEYE i Pléiades Neo,
- ground tracki na powierzchni elipsoidy WGS84,
- opcjonalne pełne orbity 3D,
- bieżące punkty podsatelitarne,
- punkty i poligony AOI,
- ostatnio obliczone okna dostępu,
- przybliżone nominalne footprinty trybów,
- akwizycje wybrane przez Greedy albo CP-SAT.

## Przepływ danych

```text
CelesTrak OMM -> SGP4 -> SatelliteGroundTrack
                          |
AOI + access windows -----+--> CZML -> CesiumJS
                          |
publiczny harmonogram ----+
```

`app/visualization/czml.py` odpowiada za budowę CZML. Moduł
`app/ui/components/cesium_globe.py` osadza renderer CesiumJS w komponencie
HTML Streamlit. Logika propagacji pozostaje niezależna od frontendu.

## Widoczność Ziemi i tryb awaryjny

Renderer zawsze ustawia niebieską elipsoidę WGS84 jako warstwę bazową.
OpenStreetMap jest dokładany jako opcjonalna warstwa sieciowa. Jeżeli
kafelki nie zostaną pobrane, globus nadal pozostaje widoczny i nie zlewa
się z czarnym tłem.

Domyślna kamera pokazuje całą Ziemię z perspektywą skierowaną na Europę.
Przycisk `Pokaż Ziemię` przywraca ten widok, natomiast `Cała scena`
dopasowuje kamerę do wszystkich obiektów CZML.

## Interpretacja warstw

- czerwone punkty i orbity: ICEYE SAR,
- niebieskie punkty i orbity: Pléiades Neo EO,
- cienkie linie na powierzchni: ground tracki,
- żółte obiekty: AOI i zlecenia,
- pomarańczowe wiązki i footprinty: geometryczne okna dostępu,
- zielone wiązki: akwizycje wybrane do harmonogramu.

Ground track jest dzielony na antymeridianie, aby uniknąć błędnych linii
przebiegających przez pół globu. Footprint jest elipsą o wymiarach
wynikających z nominalnej sceny trybu. Nie stanowi operacyjnego modelu
wiązki ani dokładnie obróconego poligonu akwizycji.

## Sterowanie

W głównym panelu pozostają tylko ustawienia potrzebne podczas pracy:

- czas początku,
- horyzont,
- wybór satelitów,
- warstwy ground tracków, orbit, AOI, okien i planu.

Krok propagacji, wysokość komponentu i footprinty są przeniesione do
`Ustawień zaawansowanych`.
