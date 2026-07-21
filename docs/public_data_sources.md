# Publiczne źródła danych

## CelesTrak

Aplikacja pobiera publiczne GP/OMM zgodnie z dokumentacją CelesTrak i standardem
CCSDS [R1], [R2], a następnie propaguje je modelem SGP4 [R3]. Snapshot ma
czas pozyskania i jest przechowywany w cache. Elementy orbitalne szybko tracą
aktualność, dlatego raport powinien zawierać ich epokę.

## ICEYE

Profile trybów i zakresy geometryczne są modelami opartymi na publicznej
dokumentacji producenta [R11]. Nie stanowią dostępu do API taskingowego ani
gwarancji wykonania zlecenia.

## Pléiades Neo

Model EO wykorzystuje publiczne parametry produktów i systemu opisane
w materiałach Airbus [R12]. Dostępność komercyjna operatora pozostaje poza
zakresem aplikacji.

## Open-Meteo

Prognoza `cloud_cover` z Open-Meteo [R13] jest używana tylko dla EO. Poligon
może być próbkowany w
kilku punktach, a wynik agregowany jako średnia, maksimum lub percentyl 75.

## STK

STK jest zewnętrznym narzędziem referencyjnym do porównania Access i AER
zgodnie z dokumentacją Ansys [R14], [R15].
Podstawowy pipeline nie wymaga zainstalowanego STK.

## Reprodukowalność

Archiwum projektu powinno zachować snapshot OMM, prognozę, konfigurację solvera,
parametry sensorów, wersję aplikacji i random seed. Ponowne pobranie danych
publicznych w innym terminie może dać inny wynik.

Oznaczenia [R1]–[R15] odnoszą się do [bibliografii projektu](references.md).
