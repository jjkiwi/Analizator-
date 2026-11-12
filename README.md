# Analizator CFD

Analiza rynku i sygnały dla CFD i akcji w XTB: technika, fundamenty, newsy, kalendarz makro.
Nie składa zleceń. Decyzja i transakcja są po stronie użytkownika.

## Stan: v0.4 (bez bota)

Adaptery sieciowe są sprawdzone na żywych danych; wyniki i ograniczenia: `CLAUDE_CODE/WYNIKI.md`, otwarte pytania: `DECYZJE.md`.
**Walidacja nie wykazała przewagi żadnej z trzech strategii ani żadnego filtra kontekstowego**, dlatego program niczego
nie rekomenduje: pokazuje sygnały razem ze zmierzoną skutecznością i zbiera dane do dalszej oceny.

## Architektura (bez własnego serwera)

```
Yahoo / Binance ───────────┐
RSS (5 języków) ───────────┤   GitHub Actions: Python co 30 min
kalendarz makro ───────────┼─▶ makro → newsy → skan → dziennik (z kontekstem) ─▶ ekran „stan na teraz”
FRED / EIA / CFTC ─────────┘   raz dziennie: bias fundamentalny, fundamenty spółek   (artefakt lub GitHub Pages)
```

- **Bez alertów.** Tor szybki (funkcje Supabase, TypeScript, Telegram) został usunięty decyzją z 2026-11-12.
- **Ekran** (`cfd now`): sygnały z ostatnich zamkniętych świec, przy każdym zmierzona skuteczność z walidacji,
  kontekst, fundamenty posiadanych spółek, kalendarz makro i newsy jako tło.
- **Dziennik**: każdy sygnał zapisany z kontekstem (technika, newsy, makro) i rozliczany po fakcie (`cfd journal-context`).
- **Bezpiecznik**: `scan.alert_strategies` jest puste; program nie składa zleceń.
- **Konfiguracja**: `config/*.yaml` to jedyne źródło prawdy.

## Zakres

72 instrumenty: 18 indeksów, 16 surowców, 4 metale szlachetne, 3 kryptowaluty, 31 akcji.
Interwały: D1, H4, H1, M30. Strategie: `trend_pullback`, `donchian_breakout`, `mean_reversion`.

## Praca lokalna

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]" && pytest
cp .env.example .env
```

```bash
cfd check-sources                 # które mapowania źródeł działają
cfd fetch --interval 1d           # historia do cache
cfd backtest GOLD --strategy donchian_breakout
cfd walkforward US500 --strategy trend_pullback
cfd report --interval 1d          # reports/walidacja_1d.html
cfd scan --interval 4h            # sygnały z ostatniej zamkniętej świecy
cfd regime                        # trend / konsolidacja

cfd news check-feeds | poll | list
cfd macro refresh | upcoming | set-actual --name "cpi" --value 0.4
cfd bias check | update | show

cfd run --once --jobs scan --intervals auto   # to samo, co robi GitHub Actions
cfd run                                       # praca ciągła na własnej maszynie (wszystkie tory w Pythonie)
cfd sync pull | push | both                   # wymiana z Supabase
cfd now                                       # ekran „stan na teraz” (reports/teraz.html)
cfd stocks update | show --details            # fundamenty spółek
cfd context-test                              # test filtra kontekstowego
cfd journal | journal-context | health | dashboard
```

## Struktura

```
config/                 instruments, settings, feeds, keywords, macro_rules, fundamentals, llm
src/cfd/                data, features, strategies, backtest, validation, news, macro, fundamentals,
                        fusion, journal, scanner, runner, notify, sync, report, dashboard, db, cli
supabase/migrations/    schemat Postgres z RLS (pozostałość po v0.3: używany tylko z kontem Supabase i panelem web/)
walidacja/              wyniki walk-forward czytane przez ekran „stan na teraz”
.github/workflows/      testy, skan (co 30 min), dzienne (bias, raport walidacji)
web/                    panel PWA (tryb demo, dopóki web/config.js jest pusty)
CLAUDE.md, CLAUDE_CODE/ instrukcja i zadania do wykonania na komputerze
DECYZJE.md              decyzje podjęte i otwarte
```

## Znane ograniczenia

- Ceny pochodzą z kontraktów futures, indeksów kasowych i giełd, nie z kwotowań XTB. Poziomy przelicz w xStation.
- Koszty w konfiguracji to założenia, dopóki nie zostaną przepisane ze specyfikacji XTB (zadanie B2).
- M30: ~60 dni darmowej historii, więc brak walidacji; harmonogram GitHuba bywa opóźniony.
- Yahoo podaje kontrakty ciągłe bez korekty rolowania: możliwe sztuczne skoki ceny.
- Darmowe newsy docierają z opóźnieniem od kilkudziesięciu sekund do kilku minut.
- Nazwy modeli i limity w `config/llm.yaml` są niesprawdzone i szybko się dezaktualizują.
- Odczyty makro po publikacji: darmowe źródło jeszcze nieznalezione (zadanie D2).
- Reguły makro i składowe biasu to podręcznikowe heurystyki. Fundamenty spółek jeszcze niezaimplementowane.
- Logika toru szybkiego istnieje w Pythonie i TypeScripcie: zmiany trzeba wprowadzać w obu.
