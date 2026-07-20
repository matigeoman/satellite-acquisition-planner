# Architektura systemu

## Warstwy

```mermaid
flowchart TB
    UI[app/ui\nStreamlit] --> SVC[app/services\nprzypadki użycia]
    SVC --> PLN[app/planning\nGreedy i CP-SAT]
    SVC --> INT[app/integrations\norbity, dostęp, pogoda, STK]
    SVC --> ANA[app/analysis\nKPI i porównania]
    SVC --> PROJ[app/projects\narchiwa]
    SVC --> REP[app/reporting\nHTML DOCX XLSX]
    PLN --> MOD[app/models\nmodele domenowe]
    INT --> MOD
    ANA --> MOD
    IO[app/io\nJSON i pliki] --> MOD
    CFG[app/config\nścieżki] --> SVC
```

## Zasady zależności

- modele domenowe nie zależą od Streamlit,
- algorytmy planowania otrzymują komplet danych przez kontrakty usług,
- integracje zewnętrzne są izolowane w `app/integrations`,
- UI inicjuje przypadki użycia, ale nie implementuje logiki solvera,
- dane generowane trafiają do `data/generated`, a nie do katalogów wejściowych,
- raportowanie i archiwizacja operują na zwalidowanych snapshotach.

## Przepływ publiczny

```mermaid
sequenceDiagram
    participant U as Użytkownik
    participant UI as Streamlit
    participant O as CelesTrak/SGP4
    participant A as Access
    participant W as Open-Meteo
    participant P as Planner
    U->>UI: AOI i zlecenie
    UI->>O: pobierz OMM i propaguj
    O-->>UI: trajektorie
    UI->>A: wyznacz okna
    A-->>UI: access windows
    UI->>W: zachmurzenie EO
    W-->>UI: forecast
    UI->>P: okazje + ograniczenia
    P-->>UI: harmonogram i diagnostyka
```

## Renderowanie globusa

Aktywny renderer używa Plotly. Pliki związane z wcześniejszym prototypem Cesium
pozostają wyłącznie jako kod historyczny i nie są importowane przez bieżącą
stronę `Globus i orbity`.
