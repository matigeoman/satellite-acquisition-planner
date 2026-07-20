# Demo i kontrola wydania

## Scenariusz demonstracyjny `POLAND_DEMO`

Zakładka **Demo i kontrola wydania** ładuje deterministyczny scenariusz
`POLAND_DEMO` bez połączenia z CelesTrak ani Open-Meteo. Scenariusz obejmuje
48 godzin i zawiera:

- 6 modelowych satelitów: 4 SAR oraz 2 EO,
- 50 zleceń: 20 SAR, 20 EO, 5 `DUAL_OPTIONAL` i 5 `DUAL_REQUIRED`,
- okna realizacji o długościach od 2 do 48 godzin,
- 500 okazji akwizycyjnych, w tym przypadki celowo niewykonalne,
- zapisany snapshot OMM oraz referencyjne okna dostępu wyznaczone przez SGP4,
- gotowe harmonogramy Greedy i CP-SAT,
- przykład benchmarku, walidacji STK i raportu HTML.

Po wczytaniu demo stan sesji zawiera zlecenia i AOI, dane orbitalne, wynik
obliczeń access, harmonogram, metadane projektu oraz pierwszą wersję historii
harmonogramu. Globus automatycznie przyjmuje 48-godzinny horyzont, dzięki czemu
widoczne są pełne ground tracki i referencyjne odcinki okien dostępu.

Wszystkie artefakty demonstracyjne znajdują się w:

```text
examples/poland_demo/
```

Dane mają charakter modelowy i nie potwierdzają komercyjnej dostępności
taskingu operatorów.

## Odtworzenie danych demo

Źródłowy generator jest deterministyczny:

```powershell
python .\scripts\generate_poland_demo.py
```

Po zmianie generatora należy ponownie uruchomić testy, ponieważ pliki w
`data/scenarios/poland_demo/` i `examples/poland_demo/` są wersjonowanymi
artefaktami referencyjnymi.

## Jedno polecenie do testów

Na Windows wszystkie kontrole lokalne można uruchomić jednym skryptem:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\verify_poland_demo.ps1
```

Wariant z przebudowaniem obrazu i sprawdzeniem healthchecku kontenera:

```powershell
.\scripts\verify_poland_demo.ps1 -Docker
```

Uruchomienie aplikacji po testach:

```powershell
.\scripts\verify_poland_demo.ps1 -StartApp
```

## Kontrola E2E

Polecenie:

```powershell
python -m app.cli release-check
```

wykonuje kolejno:

1. audyt repozytorium,
2. wczytanie scenariusza `POLAND_DEMO`,
3. dekodowanie snapshotu OMM,
4. próbną propagację SGP4 i walidację referencyjnych okien dostępu,
5. kontrolę przejścia danych zachmurzenia EO do okazji akwizycyjnych,
6. planowanie Greedy i CP-SAT dla 50 zleceń,
7. dynamiczne przeplanowanie z dwugodzinnym oknem zamrożonym,
8. eksport oraz ponowną walidację archiwum projektu,
9. wygenerowanie pakietu raportowego HTML, DOCX, XLSX i JSON.

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
`*.bak-stage*`. Opcja `--dry-run` wyświetla listę bez usuwania. Przed użyciem
należy sprawdzić `git status`; skrypt nie zastępuje kontroli zmian w Git.
