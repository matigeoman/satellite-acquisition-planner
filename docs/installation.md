# Instalacja

## Wymagania

- Python 3.11 albo Docker Desktop;
- Windows 10/11, Linux lub macOS;
- połączenie internetowe tylko dla aktualnych orbit i pogody;
- opcjonalnie STK do walidacji zewnętrznej.

## Docker — zalecany sposób uruchomienia

```powershell
docker compose up --build --detach
docker compose ps
```

Aplikacja działa pod adresem `http://localhost:8501`. Kontener powinien osiągnąć
status `healthy`.

Skrypt dla Windows:

```powershell
.\scripts\start_satplan.ps1
```

Pełna instrukcja znajduje się w [`docker.md`](docker.md).

## Lokalna instalacja na Windows

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt -c .\requirements-lock.txt
```

`uv` i Conda nie są wymagane. `requirements-dev.txt` instaluje aplikację,
interfejs, raportowanie, testy i Ruff. Plik `requirements-lock.txt` ogranicza
bezpośrednie zależności do wersji użytych w referencyjnej walidacji.

## Kontrola instalacji

```powershell
python -m app.cli check
python -m app.cli audit
python -m pytest -q
python -m ruff check app tests streamlit_app.py scripts
```

## Uruchomienie lokalne

```powershell
python -m streamlit run .\streamlit_app.py
```

## Tryb bez interfejsu

```powershell
python -m app.cli plan --scenario EXAMPLE --algorithm GREEDY
python -m app.cli plan --scenario EXAMPLE --algorithm CP_SAT
```

## Aktualizacja projektu paczką ZIP

1. Zatrzymaj Streamlit albo kontener.
2. Zatwierdź bieżące zmiany w Git lub wykonaj kopię katalogu.
3. Rozpakuj paczkę do osobnego katalogu.
4. Porównaj zmiany i przenieś je przez Git albo zastosuj dostarczony patch.
5. Ponownie zainstaluj zależności, gdy zmieniły się pliki requirements.
6. Uruchom pełną kontrolę wydania.
