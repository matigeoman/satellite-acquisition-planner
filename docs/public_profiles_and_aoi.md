# Publiczne profile sensorów i edytor AOI

Pierwszy etap integracji danych publicznych dodaje dwa profile:

- `ICEYE_PUBLIC_PROFILE` — dziewięć trybów SAR z ICEYE Product
  Documentation 6.0.7,
- `PLEIADES_NEO_PUBLIC_PROFILE` — profil optyczny PAN, MS i
  pansharpened oparty na Pléiades Neo User Guide.

Każda grupa parametrów ma oznaczone pochodzenie:

- `PUBLIC_DATA` — wartość bezpośrednio z publicznej dokumentacji,
- `MODEL_DERIVED` — jawne założenie lub wartość wyprowadzona do modelu,
- `TLE_PENDING` — parametr orbitalny zostanie zastąpiony aktualnym OMM/TLE.

## Edytor AOI

Zakładka **Cele i zlecenia** pozwala:

- narysować punkt, prostokąt lub poligon,
- edytować i usuwać geometrię,
- wpisać punkt ręcznie,
- zaimportować i wyeksportować GeoJSON,
- utworzyć walidowane `ObservationRequest`.

Prostokąt Leaflet jest zapisywany jako `Polygon`. Wszystkie współrzędne
są przechowywane w WGS84 w kolejności GeoJSON `[longitude, latitude]`.

## Ograniczenia etapu

Profile nie są jeszcze przypisane do bieżących numerów NORAD. Szablony
orbit służą wyłącznie interfejsowi. Kolejny etap pobierze aktualne GP/OMM,
wykona propagację SGP4 i wygeneruje `AcquisitionOpportunitySet`.
