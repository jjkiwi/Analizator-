# Analizator CFD: instrukcja dla Claude Code

Narzędzie do analizy rynku i sygnałów dla CFD w XTB. Użytkownik handluje ręcznie.
Kod w `src/cfd/`, konfiguracja w `config/`, testy w `tests/`. Opis modułów: `README.md`.

## Co masz zrobić

Wykonaj po kolei zadania z `CLAUDE_CODE/ZADANIA.md`. To rzeczy, których nie dało się zrobić
w środowisku bez dostępu do sieci: cały kod sieciowy powstał "na ślepo" i nigdy nie rozmawiał
z prawdziwym serwisem. Zakładaj, że adaptery zawierają błędy, dopóki ich nie sprawdzisz.

Wyniki zapisuj w `CLAUDE_CODE/WYNIKI.md` (jedna sekcja na zadanie: co zrobione, co wyszło,
co zmienione w kodzie, co nie działa). Pytania i blokady dopisuj do `DECYZJE.md` w sekcji
"Nowe pytania". Nie czekaj na odpowiedź: przejdź do następnego zadania.

## Zasady, których nie wolno łamać

1. **Żadnego składania zleceń** i żadnej integracji z rachunkiem maklerskim.
2. **Nie scrapuj XTB ani xStation** i niczego za logowaniem. XTB wyłączyło API w marcu 2025.
3. **Scraping tylko stron publicznych**, zgodnie z robots.txt i regulaminem, z odstępem
   co najmniej kilku sekund między zapytaniami do jednego serwisu. Kolejność: API → RSS → scraping.
4. **Tylko darmowe źródła.** Nic płatnego bez zgody użytkownika (wpisz pytanie do `DECYZJE.md`).
5. **Sekrety wyłącznie w `.env`** (jest w `.gitignore`). Nie wypisuj ich w logach ani w `WYNIKI.md`.
6. **Nie poluzowuj walidacji, żeby strategia "przeszła".** Progi w `validation/walkforward.py`
   i siatki w `strategies/__init__.py` zmieniaj tylko z uzasadnieniem zapisanym w `WYNIKI.md`.
   Wynik "żadna strategia nie przechodzi" jest poprawnym i cennym wynikiem.
7. **Nie dopisuj strategii do `alert_strategies`.** To decyzja użytkownika po obejrzeniu raportu.
8. **Testy muszą przechodzić** po każdej zmianie (`pytest`). Do każdej poprawki adaptera dopisz test
   na zapisanej próbce prawdziwej odpowiedzi (`tests/fixtures/`), żeby testy nie wymagały sieci.
9. Wskaźniki i strategie nie mogą zaglądać w przyszłość. Są na to testy (`*_causal`, `*_look_ahead`): nie usuwaj ich.

## Start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest                                              # oczekiwane: 57 passed
git init && git add -A && git commit -m "v0.2 z czatu"
cp .env.example .env                                # klucze uzupełnia użytkownik, patrz DECYZJE.md
```

## Konwencje

- Python 3.11+, typy, krótkie docstringi po polsku, identyfikatory po angielsku.
- Każde źródło danych za adapterem z jasnym błędem (`DataSourceError`), nigdy cichy pusty wynik.
- Czas zawsze w UTC. Ostatnia świeca z sieci jest traktowana jako niedomknięta.
- Małe commity, jeden na zadanie.
