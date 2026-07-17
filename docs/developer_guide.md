# Przewodnik deweloperski

## Środowisko

```powershell
conda activate satplan
python -m pip install -r .\requirements-dev.txt
```

## Kontrola przed commitem

```powershell
pytest -q
ruff check app tests streamlit_app.py scripts
python -m app.cli check
python -m app.cli audit
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

- ustawiaj random seed,
- nie opieraj testów na aktualnym czasie bez kontrolowanej wartości,
- nie wykonuj żądań sieciowych w testach jednostkowych,
- używaj fixture lub publicznego snapshotu testowego,
- dla CP-SAT preferuj jeden wątek w testach porównawczych.

## Paczki aktualizacyjne

Paczka etapowa powinna zawierać wyłącznie pliki nowe lub zmienione. Po jej
utworzeniu należy nałożyć ją na czystą kopię poprzedniego etapu i ponownie
uruchomić cały zestaw kontroli.
