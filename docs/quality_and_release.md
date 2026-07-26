# Kontrola jakości i wydania

## Pełna walidacja

```powershell
.\scripts\verify_release.ps1
```

Wariant z czystym buildem obrazu Docker:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Skrypt pobiera numer wydania z pliku `VERSION`, zatrzymuje się po pierwszym
błędzie i domyślnie wyłącza kontener po zakończeniu. Parametr
`-KeepContainer` pozostawia go uruchomionego.

## Polecenia składowe

```powershell
python -m pip check
python -m pytest -q
python -m scripts.check_coverage .\coverage.json
python -m pyright
python -m ruff check app tests streamlit_app.py scripts
python -m pip_audit --strict --progress-spinner off
python -m app.cli check
python -m app.cli audit --strict
python -m app.cli health --skip-http
python -m app.cli release-check --algorithm ALL --cp-sat-time-limit 2
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

Workflow `quality` uruchamia na Pythonie 3.11 testy z pomiarem coverage,
osobny próg dla krytycznej warstwy orbitalnej, Pyright, rozszerzony Ruff,
`pip-audit`, kontrolę danych, audyt i E2E. Raport `coverage.json` jest
publikowany jako artefakt przebiegu. Workflow `docker` sprawdza konfigurację
Compose, buduje obraz, oczekuje na healthcheck i wykonuje kontrole wewnątrz
kontenera. Dependabot raz w tygodniu sprawdza zależności Python, Docker oraz
GitHub Actions.

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
- testy przechodzą przy globalnym coverage co najmniej 60%;
- krytyczna warstwa orbitalna utrzymuje coverage co najmniej 65%;
- Pyright, rozszerzony Ruff i `pip-audit` przechodzą;
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
