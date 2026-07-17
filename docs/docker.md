# Docker i uruchamianie jednym poleceniem

## Zakres

Obraz kontenera zawiera Python 3.11, Streamlit, OR-Tools CP-SAT, Plotly,
biblioteki raportowe i pełny kod aplikacji. Kontener działa jako użytkownik
nieuprzywilejowany `satplan` o UID/GID `10001`.

## Wymagania

- Docker Desktop na Windows lub macOS albo Docker Engine na Linux,
- Docker Compose v2 dostępny jako `docker compose`,
- wolny port TCP, domyślnie `8501`.

## Uruchomienie na Windows

Najprostsza metoda:

```powershell
.\scripts\start_satplan.ps1
```

Skrypt:

1. sprawdza obecność Docker i Compose,
2. buduje obraz `satplan:1.0.0-rc2`,
3. uruchamia usługę w tle,
4. czeka na stan `healthy`,
5. wyświetla adres aplikacji.

Dostępne opcje:

```powershell
.\scripts\start_satplan.ps1 -Port 8601
.\scripts\start_satplan.ps1 -OpenBrowser
.\scripts\start_satplan.ps1 -NoBuild
.\scripts\start_satplan.ps1 -Foreground
```

Można także użyć pliku BAT:

```cmd
scripts\start_satplan.bat
```

## Uruchomienie przez Compose

```powershell
docker compose up --build --detach
```

Aplikacja będzie dostępna pod adresem:

```text
http://localhost:8501
```

Zmiana portu hosta:

```powershell
$env:SATPLAN_PORT = "8601"
docker compose up --build --detach
```

Wewnątrz kontenera Streamlit zawsze nasłuchuje na porcie `8501`.

## Stan i logi

```powershell
docker compose ps
docker compose logs -f satplan
docker inspect --format "{{.State.Health.Status}}" satplan
```

Pełna kontrola środowiska wewnątrz kontenera:

```powershell
docker compose exec satplan python -m app.cli health
docker compose exec satplan python -m app.cli check
docker compose exec satplan python -m app.cli audit --strict
```

## Trwałe dane

Compose tworzy nazwane wolumeny:

```text
satplan_generated
satplan_imports
```

Przechowują one:

- cache orbit,
- raporty i harmonogramy generowane przez CLI,
- benchmarki,
- importy STK.

Zwykłe zatrzymanie nie usuwa danych:

```powershell
.\scripts\stop_satplan.ps1
```

Usunięcie kontenera wraz z trwałymi wolumenami:

```powershell
.\scripts\stop_satplan.ps1 -RemovePersistentData
```

Ta operacja jest nieodwracalna dla danych znajdujących się wyłącznie w
wolumenach. Projekty i raporty pobrane wcześniej z interfejsu pozostają na
dysku użytkownika.

## Kopiowanie wyników z kontenera

Cały katalog wynikowy można skopiować na hosta:

```powershell
New-Item -ItemType Directory -Force .\satplan-container-export | Out-Null
docker compose cp `
    satplan:/opt/satplan/data/generated/. `
    .\satplan-container-export
```

Importy STK:

```powershell
docker compose cp `
    satplan:/opt/satplan/data/imports/. `
    .\satplan-import-export
```

## Healthcheck

Polecenie:

```powershell
python -m app.cli health
```

sprawdza jednocześnie:

- wersję Pythona,
- wykonanie małego modelu OR-Tools CP-SAT,
- wczytanie scenariusza `EXAMPLE`,
- możliwość zapisu do katalogów trwałych,
- odpowiedź endpointu Streamlit `/_stcore/health`.

Podczas budowy obrazu kontrola HTTP jest pomijana:

```powershell
python -m app.cli health --skip-http
```

## Budowa obrazu bez Compose

```powershell
docker build `
    --build-arg APP_VERSION=1.0.0-rc2 `
    --tag satplan:1.0.0-rc2 `
    .
```

Uruchomienie:

```powershell
docker run --rm `
    --publish 8501:8501 `
    --name satplan `
    satplan:1.0.0-rc2
```

W tym wariancie bez dodatkowych wolumenów dane z warstwy zapisywalnej kontenera
znikną po jego usunięciu.

## Bezpieczeństwo i odtwarzalność

- aplikacja nie działa jako `root`,
- włączono `no-new-privileges`,
- katalog tymczasowy jest osobnym `tmpfs`,
- obraz bazuje na `python:3.11-slim`,
- zależności są instalowane z `requirements-ui.txt`,
- podczas budowy uruchamiane są `check`, `audit --strict` i kontrola runtime,
- obraz nie zawiera cache testów, środowisk lokalnych ani wygenerowanych danych.

## GitHub Actions

Workflow `.github/workflows/docker.yml`:

1. sprawdza składnię Compose,
2. buduje obraz,
3. uruchamia kontener testowy,
4. czeka na stan `healthy`,
5. wykonuje `app.cli check` i `app.cli health` wewnątrz obrazu.
