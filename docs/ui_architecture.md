# Architektura interfejsu Streamlit

`streamlit_app.py` konfiguruje stronę, ładuje wspólne style i deleguje
renderowanie do wybranego modułu. Logika domenowa pozostaje w serwisach i
pakietach planowania.

## Nawigacja

Panel boczny dzieli moduły na trzy grupy:

### Przepływ operacyjny

- Start i demo
- Cele i zlecenia
- Orbity i dane OMM
- Okna dostępu i pogoda
- Globus operacyjny
- Śledzenie i przeloty
- Planowanie na danych publicznych
- Przeplanowanie na danych publicznych

### Analiza i walidacja

- Walidacja względem STK
- Benchmarki
- Planowanie scenariuszy referencyjnych
- Przeplanowanie scenariuszy referencyjnych
- Analiza zakłóceń
- Eksperymenty porównawcze

### Projekt i wyniki

- Projekty
- Raporty

## Moduły wspólne

- `app/ui/app_context.py` — buforowane serwisy i stan scenariusza;
- `app/ui/common.py` — formatowanie i obsługa czasu UTC;
- `app/ui/navigation.py` — grupy i etykiety nawigacji;
- `app/ui/styles.py` — ładowanie wspólnego CSS;
- `app/ui/assets/application.css` — typografia i układ kontrolek;
- `app/ui/components/` — komponenty wielokrotnego użytku;
- `app/ui/pages/` — ekrany przypadków użycia.

Ekrany nie implementują algorytmów optymalizacyjnych. Przygotowują dane
wejściowe, wywołują serwisy i prezentują wyniki. Wskaźniki udziałowe są
przechowywane jako wartości `0–1`; przeliczenie na procenty odbywa się dopiero
w warstwie prezentacji.
