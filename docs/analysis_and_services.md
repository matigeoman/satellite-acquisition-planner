# Architektura analizy i usług

## Analiza harmonogramu

Publiczny interfejs analizy znajduje się w pakiecie:

```python
from app.analysis.schedule import (
    ScheduleAnalysis,
    analyze_schedule,
    export_schedule_analysis,
)
```

Pakiet został podzielony według odpowiedzialności:

```text
app/analysis/schedule/
├── models.py      niezmienne modele KPI i kody diagnostyczne
├── analyzer.py    obliczanie KPI i diagnostyka niezrealizowanych zleceń
├── exporter.py    eksport czterech raportów CSV
└── __init__.py    publiczny interfejs pakietu
```

Plik `app/analysis/schedule_report.py` pozostaje cienką warstwą zgodności.
Dzięki temu starsze importy nadal działają, natomiast nowy kod nie zależy od
jednego dużego modułu raportowego.

## Usługi aplikacyjne

Usługi wykonują przypadki użycia, a ich niezmienne parametry i wyniki są
wydzielone do:

```text
app/services/contracts/
├── planning.py
├── replanning.py
├── comparison.py
└── __init__.py
```

Przykład zalecanego użycia:

```python
from app.services import PlanningOptions, PlanningService

result = PlanningService().run(
    scenario=scenario,
    options=PlanningOptions(),
)
```

Rozdzielenie kontraktów od implementacji daje trzy korzyści:

1. interfejs danych jest prostszy do testowania i dokumentowania,
2. moduły UI mogą importować wyniki bez zależności od szczegółów solvera,
3. zmiana implementacji usługi nie wymaga zmiany typów używanych przez resztę
   aplikacji.

## Zasada kompatybilności

Dotychczasowe importy pozostają prawidłowe:

```python
from app.analysis.schedule_report import analyze_schedule
from app.services.planning_service import PlanningOptions
```

W nowym kodzie preferowane są krótsze publiczne interfejsy:

```python
from app.analysis import analyze_schedule
from app.services import PlanningOptions
```
