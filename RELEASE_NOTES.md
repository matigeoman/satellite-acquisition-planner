# Satellite Acquisition Planner 1.1.0

Data wydania: **21 lipca 2026 r.**

Wersja `1.1.0` porządkuje interfejs aplikacji i sposób prezentowania wyników.
Model danych oraz formaty scenariuszy i archiwów pozostają zgodne z wydaniem
`1.0.1`.

## Najważniejsze zmiany

### Interfejs i globus

- zastosowano wspólny układ wizualny dla wszystkich stron Streamlit;
- uproszczono panel boczny i grupowanie modułów;
- globus operacyjny pozwala wyróżnić satelitę, wycentrować widok na Polsce,
  Europie albo wybranym obiekcie oraz sterować etykietami i warstwami;
- w widoku śledzenia dodano przełączanie między mapą globalną i globusem,
  wyróżniony ground track oraz czytelniejszy układ parametrów;
- poprawiono responsywność tabel, formularzy i paneli wynikowych.

### Benchmarki

- limity czasu CP-SAT w jednym powtórzeniu korzystają z tego samego ziarna;
- wykresy dla jednego rozmiaru problemu mają osie kategorialne;
- przyczyny niezrealizowania zleceń są agregowane według wariantu algorytmu;
- eksport zachowuje status solvera, czasy, wartości funkcji celu i informacje o
  poprawności każdego przebiegu.

### Projekty i przeplanowanie

- podgląd archiwum poprawnie liczy okazje znajdujące się w aktywnym wyniku;
- aplikacja ostrzega, gdy zapisany harmonogram obejmuje tylko część zleceń;
- puste wyniki filtrów przeplanowania są prezentowane jako komunikat, a nie
  pusta tabela.

### Repozytorium

- README opisuje Docker jako podstawową metodę uruchomienia i zwykłe `venv` jako
  metodę lokalną;
- narzędzia deweloperskie zostały oddzielone od zależności obrazu produkcyjnego;
- dodano referencyjne wersje bezpośrednich zależności dla Pythona 3.11;
- reguły audytu i sprzątania używają ogólnych wzorców zamiast nazw dawnych
  etapów i hotfixów;
- dokumentacja nie odwołuje się już do usuniętego renderera Cesium.

## Walidacja

Referencyjna kontrola:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Oczekiwany wynik końcowy:

```text
Stan: RELEASE READY
Docker status: healthy
FINAL RELEASE 1.1.0: READY
```

## Zgodność

Wersja zachowuje:

- format scenariuszy i harmonogramów `1.0.x`;
- format archiwum projektu `1.0.x`;
- interfejsy importu z `app.io` i modułów zgodnościowych;
- scenariusz `POLAND_DEMO` oraz jego dane referencyjne.

Nie jest wymagana migracja danych.

## Znane ograniczenia

- OMM/SGP4 i geometria sensora nie zastępują efemeryd ani planu operatora;
- prognoza zachmurzenia EO jest danymi zewnętrznymi i może ulec zmianie;
- parametry manewrowe i budżety zasobów są założeniami modelu;
- wynik planowania nie stanowi potwierdzenia wykonania akwizycji.

Szczegółowy opis znajduje się w
[`docs/limitations.md`](docs/limitations.md).
