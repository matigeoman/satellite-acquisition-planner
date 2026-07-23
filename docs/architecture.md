# Architektura systemu

## Warstwy i główne zależności

```mermaid
flowchart TB
    UI[app/ui<br/>Streamlit] --> SVC[app/services<br/>przypadki użycia]
    UI --> VIEW[app/visualization + app/ui/*_view<br/>prezentacja]
    SVC --> PLN[app/planning<br/>Greedy, CP-SAT, Hybrid, zasoby]
    SVC --> INT[app/integrations<br/>orbity, dostęp, pogoda, STK]
    SVC --> ANA[app/analysis<br/>KPI, benchmarki, porównania]
    SVC --> PROJ[app/projects<br/>archiwa i historia]
    SVC --> REP[app/reporting<br/>HTML, DOCX, XLSX]
    SVC --> IO[app/io<br/>JSON i pliki]
    PLN --> MOD[app/models<br/>modele domenowe]
    INT --> MOD
    ANA --> MOD
    PROJ --> MOD
    IO --> MOD
    VIEW --> MOD
    CAT[app/catalogs<br/>profile misji] --> MOD
    GEO[app/geospatial<br/>AOI i GeoJSON] --> MOD
    CFG[app/config<br/>ścieżki] --> SVC
```

## Zasady zależności

- modele domenowe nie zależą od Streamlit;
- algorytmy planowania nie importują warstwy UI;
- serwisy koordynują przypadki użycia, integracje i planery;
- integracje zewnętrzne są izolowane w `app/integrations`;
- UI nie implementuje solverów ani ograniczeń optymalizacyjnych;
- strony UI mogą korzystać z modeli domenowych, typów wynikowych i czystych
  funkcji prezentacyjnych, natomiast operacje sieciowe i orkiestracja planowania
  powinny przechodzić przez serwisy;
- dane generowane trafiają do `data/generated`, a nie do katalogów wejściowych;
- raportowanie i archiwizacja operują na zwalidowanych snapshotach.

## Przepływ publiczny

```mermaid
sequenceDiagram
    participant U as Użytkownik
    participant UI as Streamlit
    participant S as Serwisy aplikacyjne
    participant O as CelesTrak/SGP4
    participant A as Access
    participant W as Open-Meteo
    participant P as Planner
    U->>UI: AOI i zlecenie
    UI->>S: uruchom przypadek użycia
    S->>O: pobierz OMM i propaguj
    O-->>S: trajektorie
    S->>A: wyznacz okna
    A-->>S: okna dostępu
    S->>W: oceń zachmurzenie EO
    W-->>S: prognoza
    S->>P: okazje + kontakty + ograniczenia
    P-->>S: akwizycje, downlink i profil pamięci
    S-->>UI: zwalidowany wynik
```

## Przepływ zasobów danych

```mermaid
flowchart LR
    A[Akwizycja] -->|zwiększa pamięć| M[Stan pamięci satelity]
    D[Okno downlinku] -->|zmniejsza pamięć| M
    G[Stacja naziemna] --> D
    M --> P[Greedy / CP-SAT / Hybrid]
    P --> S[Harmonogram akwizycji i transmisji]
```

Modele `GroundStation`, `DownlinkOpportunity` i `DownlinkOpportunitySet` należą
do warstwy domenowej. `app/planning/resources.py` buduje profil pamięci i wpisy
transmisji, natomiast planery decydują o akwizycjach oraz — w trybie
zintegrowanym — o wykorzystaniu kontaktów. Dane scenariuszy demonstracyjnych są
syntetyczne i służą walidacji logiki, a nie geometrii radiowej.

## Renderowanie globusa

Aktywny renderer używa Plotly. Poprzedni prototyp Cesium został usunięty wraz
z nieużywanymi zasobami i testami. Strona `Globus operacyjny` korzysta wyłącznie
z bieżącej warstwy `app.visualization.plotly_globe`.
