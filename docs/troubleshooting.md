# Rozwiązywanie problemów

## Polskie znaki są zniekształcone po odczycie

Pliki projektu są UTF-8. W kodzie i testach używaj:

```python
Path(path).read_text(encoding="utf-8")
Path(path).write_text(text, encoding="utf-8")
```

Nie zapisuj plików jako ANSI lub Windows-1250.

## Test widzi inny katalog projektu

W pliku znajdującym się bezpośrednio w `tests/` katalog główny to:

```python
PROJECT_ROOT = Path(__file__).resolve().parents[1]
```

## Brak `ortools` albo `sgp4`

```powershell
python -m pip install -r .\requirements-dev.txt
```

Sprawdź, czy aktywne jest środowisko `satplan`.

## Streamlit interpretuje kolejne polecenie jako opcję

Najpierw zatrzymaj działającą aplikację przez `Ctrl+C`. Dopiero po powrocie do
promptu PowerShell uruchom `Expand-Archive`, `pytest` lub inne polecenia.

## Globus nie pokazuje podkładu geograficznego

Aktywny widok Plotly ma lokalną siatkę i powierzchnię Ziemi, więc nie wymaga
Mapbox, Cesium Ion ani zewnętrznej tekstury. Odśwież stronę i sprawdź konsolę.

## CP-SAT zwraca `UNKNOWN`

Zwiększ limit czasu, zmniejsz liczbę zleceń lub użyj jednego wątku do testu
powtarzalnego. Benchmark zapisuje taki przebieg zamiast przerywać całą serię.

## Audyt zgłasza problem

```powershell
python -m app.cli audit --json .\data\generated\reports\audit.json
```

Otwórz JSON i sprawdź `checks[].details`.
