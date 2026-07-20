# Demo i kontrola wydania

## Scenariusz demonstracyjny

Zakładka **Demo i kontrola wydania** ładuje deterministyczny scenariusz
`EXAMPLE` bez pobierania danych z Internetu. Zawiera 6 satelitów, 20 zleceń i
200 gotowych okazji akwizycyjnych dla obszarów w Polsce.

Po wczytaniu demo stan sesji zawiera:

- zlecenia i AOI,
- harmonogram Greedy albo CP-SAT,
- metadane projektu,
- pierwszą wersję historii harmonogramu.

Dzięki temu można od razu sprawdzić eksport `.satplan.zip` oraz raporty
HTML, DOCX, XLSX i JSON.

## Kontrola E2E

Polecenie:

```powershell
python -m app.cli release-check
```

wykonuje kolejno:

1. audyt repozytorium,
2. wczytanie scenariusza `EXAMPLE`,
3. planowanie Greedy i CP-SAT,
4. eksport i ponowną walidację archiwum projektu,
5. wygenerowanie pakietu raportowego.

Szybsza kontrola tylko Greedy:

```powershell
python -m app.cli release-check --algorithm GREEDY
```

Zapis artefaktów i raportu JSON:

```powershell
python -m app.cli release-check `
    --output-directory .\data\generated\release-check `
    --json .\data\generated\release-check\result.json
```

## Porządkowanie repozytorium

Skrypt:

```powershell
python .\scripts\cleanup_repository.py --project-root .
```

usuwa historyczne pliki Cesium, notatki etapów, paczki aktualizacyjne i kopie
`*.bak-stage*`. Opcja `--dry-run` wyświetla listę bez usuwania.
