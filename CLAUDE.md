# Analizator CFD: instrukcja dla Claude Code

Narzędzie do analizy rynku i sygnałów dla CFD i akcji w XTB. Użytkownik handluje ręcznie.
Opis modułów i architektury: `README.md`. Odpowiedzi użytkownika na pytania: `DECYZJE.md`.

## Architektura (bez własnego serwera, bez bota)

Decyzja z 2026-11-12: program nie wysyła alertów. Użytkownik otwiera ekran „stan na teraz”, gdy ma czas.
Tor szybki (funkcje Supabase w TypeScripcie, harmonogram `pg_cron`, Telegram) został usunięty.

- **Jeden tor**: Python (`src/cfd/`) uruchamiany przez GitHub Actions (`.github/workflows/`): kalendarz makro, newsy,
  skan techniczny, raz dziennie fundamenty. Stan roboczy w SQLite i Parquet (cache Actions i artefakt przebiegu).
- **Ekran**: `cfd now` generuje samodzielny plik HTML (`reports/teraz.html`); Actions zapisuje go jako artefakt,
  a opcjonalnie publikuje przez GitHub Pages (`.github/workflows/pages.yml`, domyślnie wyłączone).
- **Dziennik**: każdy sygnał jest zapisywany z kontekstem (technika, newsy, makro) i rozliczany po fakcie.
- **Konfiguracja**: jedno źródło prawdy w `config/*.yaml`.
- Pozostałość po v0.3, nieużywana bez konta Supabase: `supabase/migrations/`, `src/cfd/sync.py`, panel `web/`, `vercel.json`.

## Co masz zrobić

Wykonaj po kolei zadania z `CLAUDE_CODE/ZADANIA.md`. Cały kod sieciowy powstał bez dostępu do sieci
i nigdy nie rozmawiał z prawdziwym serwisem. Zakładaj, że adaptery zawierają błędy, dopóki ich nie sprawdzisz.

Wyniki zapisuj w `CLAUDE_CODE/WYNIKI.md` (jedna sekcja na zadanie: co zrobione, co wyszło, co zmienione,
co nie działa). Pytania i blokady dopisuj do `DECYZJE.md` w sekcji "Nowe pytania" i przechodź do następnego zadania.

## Zasady, których nie wolno łamać

1. **Żadnego składania zleceń** i żadnej integracji z rachunkiem maklerskim.
2. **Nie loguj się do XTB i nie scrapuj xStation.** Dozwolone jest jednorazowe odczytanie publicznej
   specyfikacji instrumentów (strona i dokumenty PDF na xtb.com) na potrzeby kosztów. Bez cyklicznego odpytywania.
3. **Scraping tylko stron publicznych**, zgodnie z robots.txt i regulaminem, z odstępem co najmniej kilku
   sekund między zapytaniami do jednego serwisu. Kolejność: API → RSS → scraping.
4. **Tylko darmowe źródła i darmowe plany.** Nic płatnego bez zgody użytkownika (pytanie do `DECYZJE.md`).
5. **Nie zakładaj kont w imieniu użytkownika** i nie akceptuj regulaminów. Jeśli brakuje konta lub klucza, odnotuj i idź dalej.
6. **Sekrety wyłącznie w `.env` i sekretach GitHub.** Nigdy w kodzie, logach, `WYNIKI.md`
   ani w `web/config.js` (tam wolno wpisać tylko adres projektu i klucz `anon`).
7. **Nie poluzowuj walidacji, żeby strategia "przeszła".** Progi i siatki parametrów zmieniaj tylko
   z uzasadnieniem zapisanym w `WYNIKI.md`. "Żadna strategia nie przechodzi" to poprawny wynik.
8. **Nie dopisuj strategii do `alert_strategies`.** To decyzja użytkownika po obejrzeniu raportu.
9. **Testy muszą przechodzić** po każdej zmianie: `pytest` (158).
   Do każdej poprawki adaptera dopisz test na zapisanej próbce prawdziwej odpowiedzi (`tests/fixtures/`).
10. Wskaźniki i strategie nie mogą zaglądać w przyszłość. Testów `*_causal` i `*_look_ahead` nie usuwaj.
11. **RLS zostaje włączone** na wszystkich tabelach. Rejestracja nowych użytkowników w Supabase Auth ma być wyłączona.

## Start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]" && pytest                   # oczekiwane: 158 passed
git init && git add -A && git commit -m "v0.3 z czatu"
cp .env.example .env                                # klucze uzupełnia użytkownik
```

## Konwencje

- Python 3.11+, typy, krótkie docstringi po polsku, identyfikatory po angielsku.
- Każde źródło danych za adapterem z jasnym błędem, nigdy cichy pusty wynik.
- Czas zawsze w UTC. Ostatnia świeca z sieci jest traktowana jako niedomknięta.
- Małe commity, jeden na zadanie.
