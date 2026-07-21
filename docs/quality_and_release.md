# Kontrola jakości i wydania

## Pełna walidacja

```powershell
.\scripts\verify_release.ps1
```

Wariant z czystym buildem obrazu Docker:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Skrypt wymaga wersji `1.1.0`, zatrzymuje się po pierwszym błędzie i domyślnie
wyłącza kontener po zakończeniu. Parametr `-KeepContainer` pozostawia go
uruchomionego.

## Polecenia składowe

```powershell
python -m pip check
pytest -q
ruff check app tests streamlit_app.py scripts
python -m app.cli check
python -m app.cli audit --strict
python -m app.cli health --skip-http
python -m app.cli release-check --algorithm BOTH --cp-sat-time-limit 2
python .\scripts\cleanup_repository.py --project-root . --dry-run
```

## Audyt repozytorium

`python -m app.cli audit` sprawdza:

- wersję Pythona i aplikacji;
- obecność wymaganych plików;
- dostępność zależności;
- UTF-8, zakończenia linii i typowe ślady mojibake;
- składnię JSON i integralność scenariuszy;
- import głównych modułów;
- katalogi wynikowe;
- Dockerfile, Compose, wolumeny i healthcheck;
- brak plików tymczasowych, paczek roboczych i wycofanych modułów.

Raport JSON:

```powershell
python -m app.cli audit `
    --strict `
    --json .\data\generated\reports\project_audit.json
```

## GitHub Actions

Workflow `quality` uruchamia testy, Ruff, kontrolę danych, audyt i E2E na
Pythonie 3.11. Workflow `docker` sprawdza konfigurację Compose, buduje obraz,
oczekuje na healthcheck i wykonuje kontrole wewnątrz kontenera.

## Healthcheck

```powershell
python -m app.cli health
```

Kontrola obejmuje środowisko Pythona, CP-SAT, dane referencyjne, możliwość
zapisu oraz endpoint Streamlit. Podczas budowy obrazu używany jest wariant
`--skip-http`.

## Kryteria wydania

- `git status` jest czysty;
- wersja w `VERSION`, Dockerze, Compose, CI i dokumentacji jest spójna;
- testy i Ruff przechodzą;
- audyt na Pythonie 3.11 nie zgłasza błędów ani ostrzeżeń;
- kontrola E2E kończy się statusem `RELEASE READY`;
- `POLAND_DEMO` działa bez sieci;
- obraz Docker przechodzi build bez cache i healthcheck;
- raporty HTML, DOCX, XLSX i JSON są generowane;
- katalog główny nie zawiera paczek aktualizacyjnych ani wyników roboczych.

## Wersjonowanie

Źródłem wersji aplikacji jest plik `VERSION`. Wersje formatów danych i archiwum
projektu są utrzymywane niezależnie, dlatego aktualizacja aplikacji nie wymaga
automatycznego podnoszenia wersji schematów.
