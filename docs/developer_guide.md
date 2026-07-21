# Przewodnik deweloperski

## Środowisko

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt -c .\requirements-lock.txt
```

## Kontrola przed commitem

```powershell
python -m pytest -q
python -m ruff check app tests streamlit_app.py scripts
python -m app.cli check
python -m app.cli audit --strict
```

## Dodawanie funkcji

1. Umieść model domenowy w `app/models`.
2. Logikę algorytmiczną dodaj do `app/planning` lub odpowiedniej integracji.
3. Przypadek użycia umieść w `app/services`.
4. UI powinno wywoływać usługę i renderować wynik.
5. Dodaj test jednostkowy oraz test architektury UI, gdy zmienia się nawigacja.
6. Zaktualizuj dokumentację i changelog.

## Kodowanie

Wszystkie pliki tekstowe zapisuj jako UTF-8 bez zależności od ustawień systemu.
Każdy `Path.read_text` i `Path.write_text` dotyczący tekstu użytkowego powinien
mieć jawne `encoding="utf-8"`.

## Determinizm

- ustawiaj jawny `random_seed`;
- nie opieraj testów na aktualnym czasie bez kontrolowanej wartości;
- nie wykonuj żądań sieciowych w testach jednostkowych;
- używaj fixture albo publicznego snapshotu testowego;
- dla CP-SAT preferuj jeden wątek w testach porównawczych;
- w jednym powtórzeniu benchmarku stosuj to samo ziarno dla wszystkich limitów
  czasu solvera.

## Przygotowanie zmian

Zmiany powinny być przekazywane jako commit lub patch wygenerowany względem
znanego commita bazowego. Przed publikacją zastosuj patch na czystej kopii,
uruchom pełny zestaw kontroli i sprawdź, czy `git status` nie zawiera plików
roboczych.
