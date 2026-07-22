# Downlink i pamięć dynamiczna

## Zakres

Wersja 1.3.0 rozszerza model planowania o jawne kontakty satelita–stacja oraz
zmienny w czasie stan pamięci. Funkcja jest przeznaczona do eksperymentów
badawczych i demonstracyjnych. Nie modeluje protokołu radiowego, kodowania,
zakłóceń, widma, kolejkowania pakietów ani rzeczywistego przydziału pasma.

## Modele danych

### Stacja naziemna

`GroundStation` zawiera:

- identyfikator i nazwę;
- szerokość, długość i wysokość;
- minimalną elewację referencyjną;
- liczbę równoległych kanałów odbiorczych;
- status aktywności oraz informację o źródle.

W bieżących scenariuszach stacje są wpisami demonstracyjnymi. Ich położenie nie
jest jeszcze używane do wyznaczania kontaktów orbitalnych. Kontakty są
przekazywane jako gotowe `DownlinkOpportunity`.

### Okno downlinku

Dla okna `w` nominalna pojemność transmisji wynosi:

\[
C_w = \frac{R_w}{8}\,\eta_w\,
\left(t_w^{end}-t_w^{start}-t_w^{setup}-t_w^{teardown}\right),
\]

gdzie:

- `R_w` — przepustowość w Mb/s;
- `η_w` — sprawność łącza w zakresie `(0,1]`;
- czasy są wyrażone w sekundach;
- dzielenie przez 8 przelicza megabity na megabajty.

Po wprowadzeniu rezerwy `r_dl` planer może wykorzystać najwyżej:

\[
C_w^{plan}=C_w(1-r_{dl}).
\]

Rezerwa reprezentuje niepewność przepustowości, narzut protokołu i margines
operacyjny. Nie jest prognozą jakości radiowej.

## Oś pamięci

Dla satelity `s` stan pamięci po zdarzeniu `k` jest liczony jako:

\[
M_s(k)=M_s(0)
+\sum_{a:\,t_a^{end}\leq t_k} D_a x_a
-\sum_{w:\,t_w^{end}\leq t_k} d_w,
\]

gdzie:

- `M_s(0)` — początkowe zajęcie pamięci;
- `D_a` — objętość danych akwizycji;
- `x_a` — binarna decyzja wyboru akwizycji;
- `d_w` — ilość danych wysłana w oknie;
- dane z akwizycji pojawiają się w pamięci po zakończeniu obrazowania;
- pamięć jest zwalniana po zakończeniu downlinku.

Dla rezerwy pamięci `r_mem` obowiązuje:

\[
0\leq M_s(k)\leq M_s^{capacity}(1-r_{mem})
\quad \text{dla każdego punktu } k.
\]

Opcja `require_full_downlink` dodaje warunek:

\[
M_s(T)=0,
\]

czyli pełne opróżnienie pamięci do końca horyzontu. Obejmuje to również dane
znajdujące się na pokładzie na początku scenariusza.

## Dostępność danych

Planer nie może wysłać danych, które powstaną dopiero po rozpoczęciu kontaktu.
W CP-SAT dla każdego okna `w` obowiązuje konserwatywny warunek:

\[
d_w + \sum_{v:\,t_v^{end}\leq t_w^{start}} d_v
\leq M_s(0)
+\sum_{a:\,t_a^{end}\leq t_w^{start}}D_a x_a.
\]

Oznacza to, że akwizycja zakończona w trakcie kontaktu nie jest przesyłana w
tym samym oknie. To świadome uproszczenie ogranicza ryzyko sztucznego
przeszacowania przepustowości.

## Konflikty kontaktów

- satelita może używać najwyżej jednego kontaktu jednocześnie;
- stacja może obsługiwać najwyżej `max_simultaneous_contacts` równoległych
  kontaktów;
- domyślnie obrazowanie i downlink na tym samym satelicie nie mogą się nakładać;
- opcja `allow_simultaneous_imaging_downlink` usuwa ostatnie ograniczenie.

Model nie rozróżnia osobnej anteny nadawczej, kierunku anteny, widma ani
przełączenia pomiędzy pasmami. Użytkownik powinien pozostawić jednoczesne
operacje wyłączone, jeśli nie ma danych potwierdzających niezależność zasobów.

## Greedy

Greedy analizuje okna chronologicznie. Wybiera kontakt, gdy:

1. satelita posiada dane na początku okna;
2. kontakt nie koliduje z już wybranym kontaktem satelity;
3. liczba równoległych kontaktów stacji pozostaje dopuszczalna;
4. kontakt nie koliduje z obrazowaniem, jeśli jednoczesność jest zabroniona.

Dane są zdejmowane z pamięci według FIFO. Wpis downlinku zawiera identyfikatory
fragmentów danych, które zostały co najmniej częściowo przesłane.

Greedy nie gwarantuje optymalnego przydziału kontaktów. Wybór najwcześniejszych
okien może być gorszy od rozwiązania globalnego, lecz jest deterministyczny i
szybki.

## CP-SAT

Dla każdego okna tworzone są:

- zmienna binarna `y_w`, czy kontakt został użyty;
- zmienna całkowita `d_w`, ile danych przesłano po skalowaniu jednostek.

Model łączy te zmienne z decyzjami akwizycji, ograniczeniami pamięci i
konfliktami kontaktów. W trybie bez wymogu pełnej dostawy solver może użyć tylko
tych kontaktów, które są konieczne do zachowania limitu pamięci. W trybie pełnej
dostawy musi wyznaczyć wystarczającą łączną objętość transmisji.

## Hybrid

Plan początkowy i każdy lokalny podproblem korzystają z tego samego zbioru
kontaktów i tych samych parametrów zasobów. Dzięki temu poprawa CP-SAT nie może
zastąpić wykonalnego profilu Greedy planem, który przekracza pamięć.

## Interfejs i eksport

Zakładka **Pamięć i downlink** pokazuje:

- liczbę wybranych kontaktów;
- sumę przesłanych danych;
- szczytowe i końcowe użycie pamięci;
- wykres zdarzeń pamięci;
- wykorzystanie planistycznej pojemności kontaktu;
- identyfikatory danych przypisanych do kontaktu.

Eksport harmonogramu zapisuje:

- `downlink_entries`;
- `resource_summaries`;
- `memory_timeline`.

Archiwum projektu zachowuje również opcjonalny `downlink_set` scenariusza.

## Źródła i charakter adaptacji

Model jest inspirowany zintegrowanym planowaniem obserwacji, pamięci i
transmisji opisanym przez Antuoriego, Wojtowicza i Hebrarda [R18], pojęciami
Mission Planning and Scheduling CCSDS [R22] oraz literaturą Satellite Range
Scheduling [R28]. Implementacja jest własna i dopasowana do modeli danych oraz
solverów Satellite Acquisition Planner.

## Ograniczenia

1. Okna w scenariuszach wbudowanych są syntetyczne.
2. Nie są wyznaczane z geometrii stacji i propagowanej orbity.
3. Przepustowość jest stała w całym kontakcie.
4. Nie modeluje się pogody radiowej, BER, modulacji ani retransmisji.
5. Ilość danych jest ciągłym zasobem po skalowaniu, a nie zbiorem pakietów.
6. CP-SAT nie przypisuje plików do kontaktów; identyfikatory są odtwarzane FIFO
   po rozwiązaniu modelu agregatowego.
7. Brak kosztu energii, temperatury i orientacji anteny podczas downlinku.
8. Planowanie stacji nie zastępuje operacyjnego systemu rezerwacji anten.
