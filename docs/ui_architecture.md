# Architektura interfejsu Streamlit

`streamlit_app.py` konfiguruje stronę, ładuje wspólne style i deleguje
renderowanie do wybranego modułu. Logika solverów i ograniczeń pozostaje w
serwisach oraz pakietach planowania.

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

- System i satelity
- Projekty
- Raporty

## Wspólna powłoka interfejsu

`application.css` definiuje typografię, odstępy, szerokości paneli, wygląd
metryk, formularzy, zakładek i tabel. Strony nie powinny nadpisywać tych reguł
lokalnym CSS, chyba że wymagają zachowania specyficznego dla danego widoku.

Strona **System i satelity** osadza lokalne diagramy SVG z katalogu
`docs/assets/diagrams` i buduje tabele bezpośrednio z publicznych profili
misji. Dzięki temu dokumentacja i interfejs korzystają z tych samych
parametrów katalogowych.

Globus operacyjny i śledzenie korzystają ze wspólnych funkcji wizualizacji
Plotly. Wyróżniony satelita, sposób centrowania i widoczność etykiet są stanem
warstwy prezentacji; nie zmieniają danych orbitalnych ani wyników planowania.

## Moduły wspólne

- `app/ui/app_context.py` — buforowane serwisy i stan scenariusza;
- `app/ui/common.py` — formatowanie i obsługa czasu UTC;
- `app/ui/navigation.py` — grupy i etykiety nawigacji;
- `app/ui/styles.py` — ładowanie wspólnego CSS;
- `app/ui/assets/application.css` — typografia i układ kontrolek;
- `app/ui/components/` — komponenty wielokrotnego użytku;
- `app/ui/pages/` — ekrany przypadków użycia.

Ekrany nie implementują algorytmów optymalizacyjnych. Przygotowują dane
wejściowe, wywołują serwisy i prezentują wyniki. Dopuszczalne są bezpośrednie
importy modeli domenowych, typów wynikowych oraz czystych funkcji
wizualizacyjnych; operacje sieciowe i uruchamianie planowania powinny być
koordynowane przez serwisy. Wskaźniki udziałowe są przechowywane jako wartości
`0–1`; przeliczenie na procenty odbywa się dopiero w warstwie prezentacji.

## System wizualny

Warstwa prezentacji używa jednego zestawu komponentów i tokenów:

- `app/ui/page_layout.py` — nagłówki stron, sekcji i paneli bocznych;
- `app/ui/plotly_theme.py` — globalny motyw wykresów Plotly;
- `app/ui/assets/application.css` — typografia, odstępy, karty, responsywność
  i stany klawiaturowe.

Każdy ekran główny zaczyna się od `render_page_header()`. Parametry umieszczone
w panelu bocznym używają zwartego `render_sidebar_heading()`. Wykresy dziedziczą
globalny motyw, chyba że wymagają specjalizowanego tła, na przykład globus 3D
lub lokalna mapa nieba.


## Interaktywne wizualizacje systemowe

Komponent `app/ui/components/system_visuals.py` odpowiada za izolowane,
responsywne wizualizacje HTML/SVG używane na stronie **System i satelity**.
Komponent fazowania:

- pobiera wartości bezpośrednio z tabeli zbudowanej ze scenariusza
  `POLAND_DEMO`;
- utrzymuje stałą separację fazową podczas animacji;
- działa bez zasobów CDN i bez dodatkowych zależności JavaScript;
- obsługuje klawiaturę, focus, pauzę, zmianę prędkości i ograniczony ruch;
- pozostawia statyczny SVG jako odpowiednik dla dokumentacji GitHub.
