# Architektura interfejsu Streamlit

Warstwa interfejsu jest oddzielona od modeli, planerów i serwisów aplikacyjnych.
`streamlit_app.py` pełni wyłącznie rolę punktu wejścia: konfiguruje stronę,
renderuje nawigację i przekazuje sterowanie do wybranego ekranu.

## Moduły

- `app/ui/app_context.py` — buforowane serwisy i wczytywanie scenariuszy.
- `app/ui/common.py` — niewielkie funkcje formatowania i obsługi czasu UTC.
- `app/ui/navigation.py` — lista modułów i panel nawigacji.
- `app/ui/styles.py` — wczytanie wspólnego arkusza CSS.
- `app/ui/assets/application.css` — typografia, szerokości i wygląd kontrolek.
- `app/ui/pages/planning.py` — planowanie oraz porównanie Greedy–CP-SAT.
- `app/ui/pages/replanning.py` — dynamiczne przeplanowanie.
- `app/ui/pages/disruption.py` — reakcja na zakłócenia.
- `app/ui/pages/experiments.py` — walidacja eksperymentalna.

Ekrany korzystają z warstwy `app/services`. Nie implementują algorytmów
optymalizacyjnych ani nie modyfikują bezpośrednio modeli domenowych.
Wskaźniki udziałowe są przechowywane jako wartości `0–1`; konwersja na procenty
odbywa się wyłącznie podczas przygotowania danych do prezentacji.
