# Scenariusz demonstracyjny POLAND_DEMO

## Zakres

Moduł **Start i demo** ładuje deterministyczny scenariusz `POLAND_DEMO` bez
połączenia z CelesTrak ani Open-Meteo. Zestaw obejmuje 48 godzin i zawiera:

- 6 modelowych satelitów: 4 SAR i 2 EO;
- 50 zleceń: 20 SAR, 20 EO, 5 `DUAL_OPTIONAL` i 5 `DUAL_REQUIRED`;
- okna realizacji od 2 do 48 godzin;
- 500 okazji akwizycyjnych, także celowo niewykonalnych;
- lokalny zestaw OMM i referencyjne okna dostępu;
- harmonogramy Greedy i CP-SAT;
- przykładowy benchmark, walidację STK i raport HTML.

Po wczytaniu dane są dostępne we wszystkich modułach aplikacji. Globus i
śledzenie satelitów automatycznie korzystają z 48-godzinnego horyzontu demo.

Pliki referencyjne znajdują się w:

```text
examples/poland_demo/
```

Dane mają charakter modelowy i nie potwierdzają komercyjnej dostępności
satelitów ani wykonania taskingu.

## Odtworzenie danych

```powershell
python .\scripts\generate_poland_demo.py
```

Generator jest deterministyczny. Po jego zmianie należy uruchomić pełne testy,
ponieważ pliki w `data/scenarios/poland_demo/` i `examples/poland_demo/` są
wersjonowanymi danymi referencyjnymi.

## Kontrola demo

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\scripts\verify_poland_demo.ps1
```

Wariant z Dockerem:

```powershell
.\scripts\verify_poland_demo.ps1 -Docker
```

## Kontrola E2E

```powershell
python -m app.cli release-check --algorithm BOTH --cp-sat-time-limit 2
```

Kontrola obejmuje:

1. audyt repozytorium;
2. wczytanie `POLAND_DEMO`;
3. dekodowanie OMM i próbną propagację SGP4;
4. okna dostępu oraz predykcję AOS/MAX/LOS;
5. przejście zachmurzenia EO do okazji;
6. planowanie Greedy i CP-SAT;
7. przeplanowanie z oknem zamrożonym;
8. eksport i ponowny import archiwum projektu;
9. raporty HTML, DOCX, XLSX i JSON.

Zapis artefaktów:

```powershell
python -m app.cli release-check `
    --algorithm BOTH `
    --output-directory .\data\generated\release-check `
    --json .\data\generated\release-check\result.json
```
