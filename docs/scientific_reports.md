# Raporty naukowe i eksport wyników

Moduł `Raporty` buduje jeden deterministyczny snapshot bieżącej sesji i renderuje go do kilku formatów:

- `report.html` — samodzielny dokument z osadzonymi wykresami;
- `report.docx` — edytowalny raport do dalszego opracowania w pracy dyplomowej;
- `results.xlsx` — pełne tabele wynikowe w osobnych arkuszach;
- `tables/*.csv` — dane źródłowe w kodowaniu UTF-8 z BOM;
- `figures/*.png` — wykresy statyczne;
- `report.json` — maszynowy snapshot raportowy.

## Dane wejściowe

Generator odczytuje wyłącznie stan bieżącej sesji Streamlit: zlecenia, snapshot OMM, okna dostępu, okazje, harmonogram, historię planów, walidację STK i benchmark algorytmów. Brak komponentu nie zatrzymuje generowania; raport zapisuje ostrzeżenie o niekompletności.

## Interpretacja

Raport automatycznie rozdziela wynik modelu publicznego od dostępności operatorskiej. OMM/GP i SGP4, publiczne profile sensorów, model footprintu oraz Open-Meteo są danymi i założeniami badawczymi. STK jest narzędziem referencyjnym do walidacji geometrii, a nie źródłem harmonogramu.
