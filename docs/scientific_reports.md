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

## Spójność snapshotu

Jeżeli stan sesji zawiera zlecenia lub metadane z wcześniejszego scenariusza,
a bieżący `PlanningResult` pochodzi z późniejszego uruchomienia planera, raport
traktuje scenariusz bieżącego harmonogramu jako źródło nadrzędne dla zleceń,
okazji, KPI i stopnia realizacji. Różnice względem metadanych projektu, listy
zleceń w interfejsie albo scenariusza benchmarku są zapisywane jako jawne
ostrzeżenia. Raport ostrzega również, gdy kolejne przeplanowanie ponownie użyło
tego samego `schedule_id`, przez co identyfikator wersji poprzedniej i bieżącej
stał się jednakowy.

Historia harmonogramów jest eksportowana w dwóch postaciach:

- skróconej — używanej w HTML, DOCX i widocznym arkuszu `Historia_planow`;
- pełnej — zachowanej w JSON, CSV oraz ukrytym arkuszu
  `Historia_szczegoly` w XLSX.

Tabele DOCX powtarzają nagłówek po przejściu na kolejną stronę i nie dzielą
pojedynczego wiersza pomiędzy stronami.
