# Kontrola jakości i wydania

## Jedno polecenie dla wydania 1.0.0

Na Windows/PowerShell w aktywnym repozytorium:

```powershell
.\scripts\verify_release.ps1
```

Pełna kontrola wraz z czystym buildem obrazu Docker:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Skrypt wymaga `VERSION=1.0.0`, zatrzymuje się po pierwszym błędzie i uruchamia wszystkie kontrole opisane poniżej. Domyślnie po teście zatrzymuje kontener. Parametr `-KeepContainer` pozostawia go uruchomionego.

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
- brak nieaktywnych modułów Cesium, notatek etapów, paczek roboczych, hotfixów, instalatorów i raportów wygenerowanych w katalogu głównym.

Raport maszynowy:

```powershell
python -m app.cli audit --json .\data\generated\reports\project_audit.json
```

`--strict` zwraca kod błędu również przy ostrzeżeniach.

## GitHub Actions

Workflow `.github/workflows/quality.yml` uruchamia się przy push i pull request. Wykonuje instalację na Pythonie 3.11, testy, Ruff, `check`, ścisły audyt oraz pełną kontrolę E2E dla Greedy i CP-SAT.

Workflow `.github/workflows/docker.yml` sprawdza Compose, buduje obraz `satplan:1.0.0`, uruchamia kontener testowy, oczekuje na pozytywny healthcheck, a następnie wykonuje `check`, ścisły audyt, healthcheck i kontrolę E2E wewnątrz kontenera.

## Wersjonowanie

Źródłem wersji jest plik `VERSION`. Moduł `app.version` udostępnia `__version__`. Archiwa projektów, raporty, obraz Docker, Compose i workflow CI używają tej samej wersji.

## Healthcheck wdrożeniowy

```powershell
python -m app.cli health
```

Kontrola obejmuje CP-SAT, scenariusz referencyjny, zapis danych oraz endpoint Streamlit. W czasie budowy obrazu używany jest wariant `--skip-http`.

## Końcowa kontrola E2E

```powershell
python -m app.cli release-check --algorithm BOTH --cp-sat-time-limit 2
```

Polecenie sprawdza scenariusz `POLAND_DEMO`, snapshot OMM, próbną propagację SGP4, referencyjne okna dostępu, mapę nieba i predykcje AOS/MAX/LOS, dane pogody EO, okazje, planowanie Greedy/CP-SAT, przeplanowanie, archiwum projektu i generator raportu. Test korzysta z lokalnych danych demonstracyjnych i nie wymaga połączenia z CelesTrak ani Open-Meteo.

## Kryteria wydania 1.0.0

- `git status` jest czysty;
- `VERSION`, dokumentacja, Docker i CI wskazują `1.0.0`;
- wszystkie testy i Ruff przechodzą;
- audyt na Pythonie 3.11 nie ma ostrzeżeń ani błędów;
- pełny E2E kończy się statusem `RELEASE READY`;
- scenariusz `POLAND_DEMO` działa bez sieci;
- obraz Docker przechodzi build bez cache, healthcheck oraz audyt wewnątrz kontenera;
- raporty HTML/DOCX/XLSX/JSON są generowane;
- nie ma tymczasowych paczek, instrukcji hotfix, kopii roboczych ani wygenerowanych raportów w katalogu głównym.

## Tag wydania

Tag należy utworzyć dopiero po pozytywnej kontroli finalnej paczki:

```powershell
git tag -a v1.0.0 -m "Satellite Acquisition Planner 1.0.0"
git push origin v1.0.0
```

Przed tagiem należy ponownie sprawdzić:

```powershell
git status
git tag --list v1.0.0
```
