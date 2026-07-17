# Układ danych i interfejs CLI

## Rozdzielenie danych

Dane źródłowe, harmonogramy referencyjne i wyniki generowane mają różny cykl życia. Z tego powodu są przechowywane osobno:

- `data/scenarios` — dane wejściowe EXAMPLE i STRESS,
- `data/reference_schedules` — wyniki kontrolne Greedy i CP-SAT,
- `data/generated` — raporty, benchmarki i harmonogramy robocze,
- `data/imports/stk` — przyszłe dane wejściowe z STK.

Centralnym rejestrem ścieżek jest `app.config.paths.ProjectPaths`.

## Główny interfejs terminalowy

Najczęstsze operacje można uruchamiać przez jeden punkt wejścia:

```powershell
python -m app.cli check
python -m app.cli paths
python -m app.cli plan --scenario EXAMPLE --algorithm GREEDY
python -m app.cli plan --scenario STRESS --algorithm CP_SAT --cp-sat-time-limit 10
```

Starsze skrypty w katalogu `scripts` pozostają dostępne dla wyspecjalizowanych eksperymentów i zgodności z dotychczasowym sposobem pracy.

## Migracja starszego katalogu `data`

```powershell
python .\scripts\migrate_data_layout.py --apply --remove-legacy
```

Skrypt najpierw kopiuje dane do nowej struktury, porównuje pliki źródłowe i docelowe, a dopiero następnie usuwa stare odpowiedniki.


## Kontrola środowiska wdrożeniowego

```powershell
python -m app.cli health --skip-http
python -m app.cli health --url http://127.0.0.1:8501/_stcore/health
```

Polecenie sprawdza Pythona, OR-Tools CP-SAT, scenariusz `EXAMPLE`, zapis do
katalogów trwałych oraz opcjonalnie endpoint Streamlit. Kod wyjścia wynosi `0`
tylko wtedy, gdy wszystkie wymagane kontrole przechodzą.
