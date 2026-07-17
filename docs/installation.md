# Instalacja

## Wymagania

- Python 3.11,
- Windows 10/11, Linux lub macOS,
- połączenie internetowe tylko dla aktualnych orbit i pogody,
- opcjonalnie STK do walidacji zewnętrznej.

## Zalecana instalacja Conda na Windows

```powershell
conda create -n satplan python=3.11
conda activate satplan
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt
```

`requirements-dev.txt` obejmuje zależności aplikacji, interfejsu, raportowania,
testów i Ruff.

## Kontrola instalacji

```powershell
python -m app.cli check
python -m app.cli audit
pytest -q
ruff check app tests streamlit_app.py scripts
```

## Uruchomienie

```powershell
streamlit run .\streamlit_app.py
```

## Tryb bez interfejsu

```powershell
python -m app.cli plan --scenario EXAMPLE --algorithm GREEDY
python -m app.cli plan --scenario EXAMPLE --algorithm CP_SAT
```

## Aktualizacja projektu paczką ZIP

1. Zatrzymaj Streamlit przez `Ctrl+C`.
2. Wykonaj kopię repozytorium lub zatwierdź bieżące zmiany w Git.
3. Rozpakuj paczkę do katalogu głównego z opcją nadpisania.
4. Ponownie zainstaluj zależności, jeśli zmieniły się pliki requirements.
5. Uruchom pełny zestaw kontroli.


## Instalacja bez lokalnego Pythona — Docker

Po zainstalowaniu Docker Desktop uruchom:

```powershell
.\scripts\start_satplan.ps1
```

Alternatywnie:

```powershell
docker compose up --build --detach
```

Pełna instrukcja, trwałe wolumeny, logi i diagnostyka znajdują się w
[`docker.md`](docker.md).
