# Kontrola jakości i wydania

## Polecenia

```powershell
pytest -q
ruff check app tests streamlit_app.py scripts
python -m app.cli check
python -m app.cli audit
```

## Audyt CLI

`audit` sprawdza:

- wersję Pythona i aplikacji,
- wymagane pliki i katalogi,
- dostępność zależności,
- poprawność UTF-8 i typowe ślady mojibake,
- składnię JSON scenariuszy i harmonogramów referencyjnych,
- integralność scenariuszy,
- import głównych modułów,
- katalogi wynikowe,
- obecność nieaktywnych modułów historycznych Cesium.

Raport maszynowy:

```powershell
python -m app.cli audit --json .\data\generated\reports\project_audit.json
```

`--strict` zwraca kod błędu również przy ostrzeżeniach.

## GitHub Actions

Workflow `.github/workflows/quality.yml` uruchamia się przy push i pull request.
Wykonuje instalację na Pythonie 3.11, testy, Ruff, `check` i ścisły audyt.

## Wersjonowanie

Źródłem wersji jest plik `VERSION`. Moduł `app.version` udostępnia
`__version__`. Archiwa projektów i raporty zapisują tę samą wersję.

## Kryteria wydania 1.0.0

- wszystkie testy i Ruff przechodzą,
- audyt na Pythonie 3.11 nie ma ostrzeżeń ani błędów,
- scenariusze referencyjne są odtwarzalne,
- dokumentacja instalacji została sprawdzona na czystym środowisku,
- raport STK zawiera co najmniej jeden pełny przypadek walidacyjny,
- benchmark ma zapisane surowe przebiegi i parametry.
