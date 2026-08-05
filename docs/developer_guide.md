# Przewodnik deweloperski

## Środowisko

```powershell
py -3.11 -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r .\requirements-dev.txt -c .\requirements-lock.txt
```

## Kontrola przed commitem

```powershell
python -m pytest -q
python -m scripts.check_coverage .\coverage.json
python -m pyright
python -m ruff check app tests streamlit_app.py scripts
python -m pip_audit --strict --progress-spinner off
python -m app.cli check
python -m app.cli audit --strict
```

## Progi jakości

- globalne coverage aplikacji: co najmniej 60%;
- łączne coverage `app/integrations/orbits/` i
  `app/services/orbit_service.py`: co najmniej 65%;
- Pyright działa w trybie `basic` dla krytycznej warstwy orbitalnej;
- Ruff obejmuje błędy wykonania, wybrane reguły Bugbear i `RUF100`;
- testy dokumentacji sprawdzają linki wewnętrzne, zapis wzorów, wspólną notację
  i zgodność podstawowych odwołań bibliograficznych;
- `pip-audit` blokuje CI przy podatnościach lub błędzie zebrania zależności.

Globalna kontrola `ruff format --check` nie jest obecnie włączona, ponieważ
historyczna baza kodu nie została jeszcze jednolicie sformatowana przez Ruff.
Jej wprowadzenie powinno nastąpić w osobnym PR-ze obejmującym wyłącznie
formatowanie, bez zmian merytorycznych.

Obniżenie progów wymaga uzasadnienia w Pull Request. Nowy kod krytyczny powinien
zwiększać lub co najmniej utrzymywać pokrycie.

## Dodawanie funkcji

1. Umieść model domenowy w `app/models`.
2. Logikę algorytmiczną dodaj do `app/planning` lub odpowiedniej integracji.
3. Przypadek użycia umieść w `app/services`.
4. UI powinno wywoływać usługę i renderować wynik.
5. Dodaj test jednostkowy oraz test architektury UI, gdy zmienia się nawigacja.
6. Zaktualizuj dokumentację i changelog.

## Kodowanie

Wszystkie pliki tekstowe zapisuj jako UTF-8 bez zależności od ustawień systemu.
Każdy `Path.read_text` i `Path.write_text` dotyczący tekstu użytkowego powinien
mieć jawne `encoding="utf-8"`.

## Wzory matematyczne w Markdown

Wzory blokowe zapisuj za pomocą delimiterów `$$` umieszczonych w osobnych
wierszach:

```markdown
$$
F_{\mathrm{Hybrid}} \geq F_{\mathrm{Greedy\,2.0}}
$$
```

Nie używaj delimiterów `\[` i `\]`. Część rendererów Markdown, w tym widoki
używane przez projekt, może potraktować je jako zwykłe nawiasy i wyświetlić
kod LaTeX zamiast wzoru.

Symbole powinny mieć jedno znaczenie w obrębie dokumentu. Dla modelu
planowania obowiązuje wspólna konwencja:

- `τ_i` — czas trwania akwizycji;
- `D_i` — objętość danych akwizycji;
- `q_w` — objętość danych wysłana w oknie kontaktu;
- `R_w` — szybkość transmisji;
- `M_s(t)` — zajętość pamięci satelity.

Powtórzony wzór powinien mieć identyczną notację we wszystkich dokumentach.
Testy w `tests/test_markdown_math.py` sprawdzają delimitery oraz kanoniczny
zapis heurystyki Greedy 2.0 i modelu pamięci dynamicznej.

## Terminologia

W tekście opisowym preferuj polski termin, a angielską nazwę lub nazwę kodową
podawaj przy pierwszym użyciu, na przykład:

- rozwiązanie bazowe (`incumbent`);
- wyszukiwanie lokalne (`local search`);
- model oparty na okazjach (`opportunity-based`);
- funkcja punktacji (`scoring`);
- ślad sensora (`footprint`);
- pamięć podręczna (`cache`).

Nazw klas, pól, statusów i parametrów konfiguracyjnych nie tłumacz.

## Bibliografia

Każda metoda opisana jako adaptacja literatury powinna wskazywać identyfikator
źródła z `docs/references.md`. Nie przypisuj publikacji funkcji, której projekt
nie implementuje. W szczególności należy odróżniać:

- inspirację metodologiczną od implementacji algorytmu jeden do jednego;
- publiczne dane operatora od parametrów `MODEL_DERIVED`;
- dokumentację standardu od walidacji dokładności;
- repozytorium referencyjne od kodu wykorzystanego bezpośrednio.

Nowe źródło powinno zawierać autora lub instytucję, pełny tytuł, rok,
wydawnictwo lub nazwę wydarzenia oraz DOI albo stabilny adres dokumentu, jeżeli
jest dostępny.

## Determinizm

- ustawiaj jawny `random_seed`;
- nie opieraj testów na aktualnym czasie bez kontrolowanej wartości;
- nie wykonuj żądań sieciowych w testach jednostkowych;
- używaj fixture albo publicznego snapshotu testowego;
- dla CP-SAT preferuj jeden wątek w testach porównawczych;
- w jednym powtórzeniu benchmarku stosuj to samo ziarno dla wszystkich limitów
  czasu solvera.

## Przygotowanie zmian

Zmiany powinny być przekazywane jako commit lub patch wygenerowany względem
znanego commita bazowego. Przed publikacją zastosuj patch na czystej kopii,
uruchom pełny zestaw kontroli i sprawdź, czy `git status` nie zawiera plików
roboczych.
