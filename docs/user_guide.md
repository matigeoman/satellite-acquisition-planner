# Instrukcja użytkownika

## Typowy przepływ pracy

```mermaid
flowchart LR
    A[Cel i AOI] --> B[Zlecenie]
    B --> C[Orbity i dane OMM]
    C --> D[Okna dostępu]
    D --> E[Pogoda EO]
    E --> F[Okazje]
    F --> G[Greedy lub CP-SAT]
    G --> H[Harmonogram]
    H --> I[Globus i raport]
```

## 1. Cele i zlecenia

Narysuj punkt, prostokąt albo poligon. Określ priorytet, przedział czasu,
wymagany typ sensora oraz — dla zleceń podwójnych — maksymalny odstęp SAR–EO.

## 2. Orbity i dane OMM

Pobierz aktualny snapshot GP/OMM. Aplikacja przypisuje publiczne obiekty do
czterech pozycji ICEYE i dwóch pozycji Pléiades Neo oraz przechowuje cache.

## 3. Okna dostępu

Wybierz horyzont, krok propagacji i tryby sensorów. Wynik jest geometrycznym
przybliżeniem dostępu. Dla EO pobierz zachmurzenie i zbuduj okazje planistyczne.

## 4. Planowanie na danych publicznych

Uruchom Greedy lub CP-SAT. Ustaw rezerwę pamięci, limit solvera i ograniczenia
operacyjne. Sprawdź harmonogram oraz diagnostykę niezrealizowanych zleceń.

## 5. Przeplanowanie na danych publicznych

Wybierz moment przeplanowania i długość okna zamrożonego. Aplikacja zachowa
operacje bliskoterminowe, odświeży pogodę EO i zoptymalizuje pozostały horyzont.

## 6. Globus operacyjny

Globus Plotly pokazuje ground tracki, bieżące pozycje satelitów, AOI, okna
dostępu i zaplanowane połączenia. Widok 3D przedstawia orbity przestrzenne.

## 7. Walidacja STK

Pobierz paczkę przypadku, odtwórz go w STK, wyeksportuj Access lub AER i
zaimportuj raport. Porównaj błędy granic okien i geometrii.

## 8. Benchmarki

Uruchom serię scenariuszy o rosnącej liczbie zleceń. Eksportuj surowe przebiegi,
podsumowania i wykresy porównujące Greedy z CP-SAT.

## 9. Projekty

Zapisz całą sesję jako `.satplan.zip`. Import jest poprzedzony kontrolą manifestu,
sum SHA-256, wersji schematu i referencji między obiektami.

## 10. Raporty

Wygeneruj pakiet HTML, DOCX, XLSX, JSON, CSV i PNG. Zakres raportu zależy od
tego, które komponenty zostały wcześniej wyliczone w bieżącej sesji.
