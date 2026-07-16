# Struktura projektu

```text
app/
├── analysis/    analiza KPI, raporty i eksperymenty
├── config/      konfiguracja ścieżek i ustawień projektu
├── io/          wczytywanie i zapis modeli danych
├── models/      modele Pydantic i walidacja domenowa
├── planning/    Greedy, CP-SAT, konfiguracja i funkcja celu
├── scenarios/   generatory scenariuszy
├── services/    przypadki użycia aplikacji
└── ui/          interfejs Streamlit

data/
├── imports/stk/       przyszłe raporty STK
├── generated/         nowe wyniki robocze
├── reports/           zachowane raporty eksperymentalne
└── benchmarks/        zachowane benchmarki

scripts/         polecenia uruchomieniowe i diagnostyczne
tests/           testy jednostkowe, integracyjne i regresyjne
```

Zależności powinny przebiegać od warstwy prezentacji i usług w kierunku modeli
i planowania. Modele domenowe nie importują Streamlit, plików raportowych ani
konkretnych ścieżek systemu plików.
