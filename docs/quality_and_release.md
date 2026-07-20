# Kontrola jakości i wydania

## Polecenia

```powershell
pytest -q
ruff check app tests streamlit_app.py scripts
python -m app.cli check
python -m app.cli audit
python -m app.cli health --skip-http
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
- kompletność Dockerfile, Compose, wolumenów i healthchecku,
- brak nieaktywnych modułów Cesium, notatek etapów, paczek roboczych i instalatorów.

Raport maszynowy:

```powershell
python -m app.cli audit --json .\data\generated\reports\project_audit.json
```

`--strict` zwraca kod błędu również przy ostrzeżeniach.

## GitHub Actions

Workflow `.github/workflows/quality.yml` uruchamia się przy push i pull request.
Wykonuje instalację na Pythonie 3.11, testy, Ruff, `check`, ścisły audyt oraz kontrolę E2E `release-check --algorithm GREEDY`.

Workflow `.github/workflows/docker.yml` sprawdza Compose, buduje obraz, uruchamia
kontener testowy i oczekuje na pozytywny healthcheck. Następnie wykonuje kontrolę
danych i runtime wewnątrz kontenera.

## Wersjonowanie

Źródłem wersji jest plik `VERSION`. Moduł `app.version` udostępnia
`__version__`. Archiwa projektów i raporty zapisują tę samą wersję.

## Healthcheck wdrożeniowy

```powershell
python -m app.cli health
```

Kontrola obejmuje CP-SAT, scenariusz referencyjny, zapis danych oraz endpoint
Streamlit. W czasie budowy obrazu używany jest wariant `--skip-http`.

## Kryteria wydania 1.0.0

- wszystkie testy i Ruff przechodzą,
- audyt na Pythonie 3.11 nie ma ostrzeżeń ani błędów,
- scenariusze referencyjne są odtwarzalne,
- dokumentacja instalacji została sprawdzona na czystym środowisku,
- obraz Docker przechodzi build i test uruchomieniowy,
- raport STK zawiera co najmniej jeden pełny przypadek walidacyjny,
- benchmark ma zapisane surowe przebiegi i parametry.

## Końcowa kontrola E2E

```powershell
python -m app.cli release-check
```

Polecenie sprawdza planowanie, archiwum projektu i generator raportu.
