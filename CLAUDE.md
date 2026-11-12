# Analizator CFD: instrukcja dla Claude Code

Narzędzie do analizy rynku i sygnałów dla CFD i akcji w XTB. Użytkownik handluje ręcznie.
Opis modułów i architektury: `README.md`. Odpowiedzi użytkownika na pytania: `DECYZJE.md`.

## Architektura docelowa (bez własnego serwera)

- **Tor szybki** (newsy, kalendarz makro, alerty): funkcje Supabase w TypeScripcie (`supabase/functions/`),
  wywoływane co minutę przez `pg_cron`.
- **Tor wolny** (świece, wskaźniki, strategie, fundamenty): Python (`src/cfd/`) uruchamiany przez GitHub Actions
  (`.github/workflows/`). Stan roboczy w SQLite i Parquet (cache Actions), wyniki wypychane do Supabase.
- **Baza wspólna**: Postgres w Supabase (`supabase/migrations/`).
- **Panel**: statyczne PWA (`web/`) na Vercel, czyta z Supabase po zalogowaniu.
- **Konfiguracja**: jedno źródło prawdy w `config/*.yaml`. Dla funkcji Supabase generuje się z niej JSON:
  `cfd export-config` → `supabase/functions/_shared/config.json`. Po każdej zmianie YAML wygeneruj i wdróż ponownie.

Logika toru szybkiego istnieje w dwóch językach (Python do pracy lokalnej, TypeScript do chmury).
Zmieniając jedną wersję, zmień drugą i jej testy.

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
6. **Sekrety wyłącznie w `.env`, sekretach GitHub i sekretach Supabase.** Nigdy w kodzie, logach, `WYNIKI.md`
   ani w `web/config.js` (tam wolno wpisać tylko adres projektu i klucz `anon`).
7. **Nie poluzowuj walidacji, żeby strategia "przeszła".** Progi i siatki parametrów zmieniaj tylko
   z uzasadnieniem zapisanym w `WYNIKI.md`. "Żadna strategia nie przechodzi" to poprawny wynik.
8. **Nie dopisuj strategii do `alert_strategies`.** To decyzja użytkownika po obejrzeniu raportu.
9. **Testy muszą przechodzić** po każdej zmianie: `pytest` (158) i `deno test supabase/tests/` (12).
   Do każdej poprawki adaptera dopisz test na zapisanej próbce prawdziwej odpowiedzi (`tests/fixtures/`).
10. Wskaźniki i strategie nie mogą zaglądać w przyszłość. Testów `*_causal` i `*_look_ahead` nie usuwaj.
11. **RLS zostaje włączone** na wszystkich tabelach. Rejestracja nowych użytkowników w Supabase Auth ma być wyłączona.

## Start

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]" && pytest                   # oczekiwane: 158 passed
deno test supabase/tests/                           # oczekiwane: 12 passed
git init && git add -A && git commit -m "v0.3 z czatu"
cp .env.example .env                                # klucze uzupełnia użytkownik
```

## Konwencje

- Python 3.11+, typy, krótkie docstringi po polsku, identyfikatory po angielsku. TypeScript bez zewnętrznych zależności.
- Każde źródło danych za adapterem z jasnym błędem, nigdy cichy pusty wynik.
- Czas zawsze w UTC. Ostatnia świeca z sieci jest traktowana jako niedomknięta.
- Małe commity, jeden na zadanie.
