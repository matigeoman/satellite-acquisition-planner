# Katalog `data`

Dane są rozdzielone według ich roli:

```text
data/
├── scenarios/
│   ├── example/
│   │   ├── system.json
│   │   ├── requests.json
│   │   └── opportunities.json
│   ├── poland_demo/
│   │   ├── system.json
│   │   ├── requests.json
│   │   └── opportunities.json
│   └── stress/
│       ├── system.json
│       ├── requests.json
│       └── opportunities.json
├── reference_schedules/
│   ├── example/
│   │   ├── greedy.json
│   │   └── cp_sat.json
│   └── stress/
│       ├── greedy.json
│       └── cp_sat.json
├── imports/
│   └── stk/
└── generated/
    ├── schedules/
    ├── reports/
    └── benchmarks/
```

## Zasady

- `scenarios` zawiera wersjonowane dane wejściowe, w tym 48-godzinny `POLAND_DEMO` z 50 zleceniami i 500 okazjami.
- `reference_schedules` zawiera stabilne wyniki używane w testach i przykładach.
- `imports/stk` jest przeznaczony na raporty wyeksportowane z STK.
- `generated` zawiera wyniki robocze i jest ignorowany przez Git poza plikami `.gitkeep`.
- Kod powinien korzystać z `app.config.paths.ProjectPaths`, a nie składać ścieżek ręcznie.
