MAP HOTFIX V2

Poprawia błąd:
ValueError: zip() argument 2 is shorter than argument 1

Przyczyna:
dla zamkniętego pierścienia listy `ring` i `ring[1:]`
mają różne długości. Poprawka porównuje:
`ring[:-1]` z `ring[1:]`.

Nadpisywane pliki:
- app/ui/map_view.py
- tests/test_map_view.py
