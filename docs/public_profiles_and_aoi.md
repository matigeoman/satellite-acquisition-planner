# Publiczne profile sensorów i edytor AOI

Pierwszy etap integracji danych publicznych dodaje dwa profile:

- `ICEYE_PUBLIC_PROFILE` — dziewięć trybów SAR z ICEYE Product
  Documentation 6.0.7 [R11],
- `PLEIADES_NEO_PUBLIC_PROFILE` — profil optyczny PAN, MS i
  pansharpened oparty na Pléiades Neo User Guide [R12].

Każda grupa parametrów ma oznaczone pochodzenie:

- `PUBLIC_DATA` — wartość bezpośrednio z publicznej dokumentacji,
- `MODEL_DERIVED` — jawne założenie lub wartość wyprowadzona do modelu,
- `PUBLIC_ORBIT_DATA` — bieżące elementy orbitalne są pobierane jako OMM i propagowane modelem SGP4.

## Edytor AOI

Zakładka **Cele i zlecenia** pozwala:

- narysować punkt, prostokąt lub poligon,
- edytować i usuwać geometrię,
- wpisać punkt ręcznie,
- zaimportować i wyeksportować GeoJSON,
- utworzyć walidowane `ObservationRequest`.

Prostokąt Leaflet jest zapisywany jako `Polygon`. Wszystkie współrzędne
są przechowywane w WGS 84 w kolejności GeoJSON `[longitude, latitude]`,
zgodnej z RFC 7946 [R16].

## Integracja z orbitami publicznymi

Profile opisują nominalne właściwości misji i sensorów. Bieżące rekordy OMM są
przypisywane do slotów planera, propagowane przez SGP4 i wykorzystywane do
śledzenia, okien dostępu oraz budowy `AcquisitionOpportunitySet`. RAAN, epoka i
mimośród zapisane w szablonie profilu nie są traktowane jako aktualna orbita.

Pełne zestawienie parametrów, fazowania i geometrii znajduje się w dokumencie
[System satelitarny, parametry i geometria](satellite_system.md).

## Zlecenia łączone SAR + EO

Formularz udostępnia cztery czytelne warianty:

- tylko SAR,
- tylko EO,
- SAR + EO wymagane (`DUAL_REQUIRED`),
- SAR + EO opcjonalne (`DUAL_OPTIONAL`).

Dla zlecenia łączonego można podać osobny limit rozdzielczości SAR i EO.
Pole `max_resolution_m` pozostaje wspólną wartością zapasową dla zgodności
z wcześniejszymi scenariuszami, a metoda `resolution_limit_for()` zwraca
limit właściwy dla typu sensora.

Oznaczenia źródeł prowadzą do [bibliografii projektu](references.md).
