# Publiczne źródła danych

## CelesTrak

Aplikacja pobiera publiczne GP/OMM i propaguje je modelem SGP4. Snapshot ma
czas pozyskania i jest przechowywany w cache. Elementy orbitalne szybko tracą
aktualność, dlatego raport powinien zawierać ich epokę.

## ICEYE

Profile trybów i zakresy geometryczne są modelami opartymi na publicznych
materiałach producenta. Nie stanowią dostępu do API taskingowego ani gwarancji
wykonania zlecenia.

## Pléiades Neo

Model EO wykorzystuje publiczne parametry orbity, rozdzielczości, pasm,
szerokości pasa i manewrowości. Dostępność komercyjna operatora pozostaje poza
zakresem aplikacji.

## Open-Meteo

Prognoza zachmurzenia jest używana tylko dla EO. Poligon może być próbkowany w
kilku punktach, a wynik agregowany jako średnia, maksimum lub percentyl 75.

## STK

STK jest zewnętrznym narzędziem referencyjnym do porównania Access i AER.
Podstawowy pipeline nie wymaga zainstalowanego STK.

## Reprodukowalność

Archiwum projektu powinno zachować snapshot OMM, prognozę, konfigurację solvera,
parametry sensorów, wersję aplikacji i random seed. Ponowne pobranie danych
publicznych w innym terminie może dać inny wynik.
