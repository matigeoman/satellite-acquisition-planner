# Warstwa I/O i ścieżki projektu

## Cel

Moduły domenowe nie powinny samodzielnie ustalać położenia katalogu projektu
ani powielać kodu wczytującego JSON. Te odpowiedzialności zostały wydzielone
do `app/config` i `app/io`.

## `app/config/paths.py`

`ProjectPaths` jest centralnym rejestrem lokalizacji danych, raportów,
benchmarków, importów STK i wyników generowanych. Obiekt może być utworzony dla
dowolnego katalogu głównego, co ułatwia testy oraz przenoszenie projektu.

## `app/io`

Warstwa zawiera wyspecjalizowane funkcje:

- `load_system_catalog`,
- `load_request_set`,
- `load_opportunity_set`,
- `load_schedule`,
- `save_schedule`.

Wspólne operacje JSON wykonuje `json_files.py`. Walidacja danych pozostaje w
modelach Pydantic.

Starsze moduły `catalog_loader.py`, `request_loader.py`,
`opportunity_loader.py` i `schedule_loader.py` pozostają jako cienkie warstwy
zgodności. Nowy kod powinien importować funkcje z `app.io`.

## Skrypty

Skrypty korzystają z jednego pliku `scripts/_bootstrap.py`. Tylko ten moduł
uzupełnia `sys.path` przy uruchamianiu pliku bez instalowania projektu jako
pakietu. Pozostałe skrypty nie powielają już tej logiki.
