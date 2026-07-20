# Satellite Acquisition Planner 1.0.1

Data wydania: **20 lipca 2026 r.**

Wersja `1.0.1` porządkuje pierwsze stabilne wydanie bez zmiany modelu
planowania ani formatów danych. Aktualizacja koncentruje się na spójności
repozytorium, dokumentacji i interfejsu.

## Zmiany

- uporządkowano nawigację Streamlit według przepływu operacyjnego, analizy oraz
  zarządzania projektem;
- ujednolicono nazwy modułów i terminologię polsko-angielską w interfejsie;
- skrócono teksty informacyjne i usunięto sformułowania o charakterze roboczym;
- zaktualizowano opis struktury projektu do rzeczywistego układu pakietów;
- połączono powielone rozdziały dotyczące benchmarków i planowania;
- usunięto nieużywany punkt wejścia `main.py`;
- usunięto nieużywane importy i rozszerzono linting o kontrolę `F401`;
- dodano `.editorconfig` i `.gitattributes`, aby jednoznacznie ustalić UTF-8
  oraz zakończenia linii na Windows i Linux;
- rozszerzono audyt repozytorium o kontrolę plików konfiguracyjnych i
  wycofanego punktu wejścia.

## Walidacja

Referencyjna kontrola wykonywana jest na Pythonie 3.11:

```powershell
.\scripts\verify_release.ps1 -Docker -NoCache
```

Oczekiwany wynik końcowy:

```text
Stan: RELEASE READY
Docker status: healthy
FINAL RELEASE 1.0.1: READY
```

## Zgodność

Aktualizacja zachowuje:

- format scenariuszy i harmonogramów `1.0.0`;
- format archiwum projektu `1.0.0`;
- istniejące interfejsy importu z `app.io` i modułów zgodnościowych;
- scenariusz `POLAND_DEMO` i jego wyniki referencyjne.

Nie jest wymagana migracja danych.

## Znane ograniczenia

- OMM/SGP4 i geometria sensora nie zastępują efemeryd ani planu operatora;
- prognoza zachmurzenia EO jest danymi zewnętrznymi i może ulec zmianie;
- parametry manewrowe oraz budżety zasobów są założeniami modelu;
- wynik planowania nie stanowi potwierdzenia wykonania akwizycji.

Szczegółowy opis: [`docs/limitations.md`](docs/limitations.md).
