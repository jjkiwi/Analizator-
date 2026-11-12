# Decyzje

Klucze i tokeny wpisuj tylko do `.env`, sekretów GitHub i sekretów Supabase. Nie do czatu i nie do tego pliku.

## Rozstrzygnięte (11.11.2026)

| # | Temat | Decyzja | Stan |
|---|---|---|---|
| 1 | Koszty XTB | ze strony specyfikacji XTB | strona ładuje tabelę JavaScriptem, stąd nie da się jej odczytać: zadanie B2 dla Claude Code |
| 2 | Gdzie działa | najpierw cron w chmurze (Supabase + GitHub Actions), później ewentualnie własna maszyna | zbudowane w v0.3, do wdrożenia |
| 3 | Telegram | później | bez tokenu alerty trafiają tylko do logów |
| 4 | Klucz FRED | jest, do wpisania w sekrety | sekret `FRED_API_KEY` w GitHub Actions |
| 5 | Trzecia kryptowaluta | Solana | wpisane |
| 6 | Akcje | z wyciągu XTB | 31 spółek dodanych, mapowania do weryfikacji (A1) |
| 7 | Cynk, nikiel | pominąć | usunięte |
| 8 | Interwały | D1, H4, H1, M30 | dodane; M30 z zastrzeżeniem (punkt 20) |
| 9 | Klasyfikacja newsów | darmowe modele | łańcuch: Gemini → Groq → OpenRouter (Kimi) → NVIDIA (Kimi) → Mistral → reguły |
| 10 | Próg alertów | pilne i istotne (waga ≥ 2) | ustawione |
| 11 | Cisza nocna | 23:00–8:00 czasu polskiego | ustawione; rano jedno podsumowanie |
| 12 | Języki | więcej | angielski, polski, niemiecki, francuski, hiszpański |
| 13 | Ceny na żywo | konto demo u brokera z API | konto musisz założyć sam (punkt 18) |
| 14 | Alerty ze strategii | po wynikach walidacji i forward testu | wszystkie strategie tylko zapisują do dziennika |
| 15 | Panel | PWA | zbudowany (`web/`), nieprzetestowany w przeglądarce |
| 16 | Kalkulator pozycji | rachunek w PLN, ryzyko do ustalenia | czeka na koszty z B2 |

## Do podjęcia

17. **Repozytorium publiczne czy prywatne?** Skan co 30 minut zużyje w prywatnym repozytorium więcej darmowych
    minut GitHub Actions, niż wynosi pula. Opcje:
    a) publiczne (Actions bez limitu; kod i lista Twoich spółek będą widoczne, kwoty i klucze nie),
    b) prywatne ze skanem co godzinę (bez M30) i kontrolą zużycia,
    c) prywatne, a listę akcji trzymać poza repozytorium (w sekrecie). Wymaga drobnej przeróbki.
    Odpowiedź: ...

18. **Konta do założenia (nie mogę zrobić tego za Ciebie).** Wszystkie darmowe:
    - Supabase (baza i funkcje), GitHub (repozytorium i Actions), Vercel (panel),
    - co najmniej jeden dostawca modeli: Google AI Studio (Gemini) lub Groq; opcjonalnie OpenRouter, NVIDIA, Mistral,
    - później: konto demo Capital.com lub IG (ceny na żywo).
    Założone: ...

19. **Sygnały SHORT na akcjach, które posiadasz.** a) pokazywać jako ostrzeżenie "rozważ redukcję",
    b) dla akcji tylko sygnały LONG, c) bez zmian. Odpowiedź: ...

20. **M30.** Darmowe dane dają tylko ~60 dni historii, więc strategii na M30 nie da się zwalidować, a harmonogram
    GitHuba bywa opóźniony o kilka–kilkanaście minut. Proponuję: M30 zbiera sygnały tylko do dziennika, bez alertów,
    dopóki nie będzie cen na żywo. Zgoda? ...

21. **ETF-y z wyciągu.** Masz też 10 ETF-ów i ETC na złoto. Indeksy i złoto są już śledzone jako CFD.
    Dodać ETF-y tematyczne (uran, metale ziem rzadkich, ropa i gaz, small cap value, Daleki Wschód)? ...

22. **Kolejne języki.** Dodać chiński lub japoński (istotne dla HK.cash, JP225, miedzi)? ...

23. **Ryzyko na transakcję** do kalkulatora pozycji (np. 1% kapitału). ...

## Nowe pytania (dopisuje Claude Code)

### Nowe pytania (zadania A1-A3)

1. **ZINC i NICKEL: brak darmowego źródła.** Yahoo nie ma kontraktów LME, a `ZNC=F` to martwa seria bez obrotu. Opcje: (a) zostawić bez danych (stan obecny, instrumenty nie są skanowane), (b) użyć jako zamiennika ETC z Londynu `ZINC.L` / `NICK.L`: dobry kierunek i procentowa zmienność, ale inna skala cen, więc poziomów SL/TP nie da się przenieść do xStation, (c) płatne źródło danych LME. Którą opcję wybrać?
2. **Stooq nie działa z tego środowiska** (strona weryfikacji przeglądarki, zrywane połączenia, 404). Proszę uruchomić u siebie `cfd check-sources` i sprawdzić wiersze `stooq`. Jeśli tam też jest BŁĄD, czy usunąć Stooq z konfiguracji? Skutek: W20 ma wtedy tylko 2 lata historii dziennej z Yahoo, reszta instrumentów nic nie traci (Yahoo jest pierwszym źródłem).
3. **W20: indeks kasowy zamiast kontraktu.** Jedyne darmowe dane intraday to `WIG20.WA` z Yahoo (1h, 730 dni). CFD W20 w XTB jest oparty na kontrakcie FW20, więc poziomy różnią się o bazę. Czy to wystarcza, czy szukać danych FW20 (darmowych nie znalazłem)?
4. **Świece rolowania.** Na gazie skok przy rolowaniu sięga kilkunastu procent (rekord −47,5% w styczniu 2026), na wieprzowinie −18%. Backtest liczy te ruchy jako zysk lub stratę, których na CFD nie ma. Maska świec rolowania jest gotowa dla ropy WTI i gazu (`roll_flags`). Czy: (a) wykluczyć świece rolowania z sygnałów i backtestu, (b) dodatkowo zrobić korektę wsteczną cen dla NATGAS i LEANHOGS, (c) zostawić jak jest? Każda z opcji (a) i (b) zmieni wyniki raportu walk-forward, dlatego nie włączałem ich sam.
5. **Stara historia bez zasięgu świec.** W wielu seriach dziennych sprzed lat Yahoo podaje tylko zamknięcia (JP225, USDIDX, platyna, pallad, srebro, DAX, aluminium). Czy obciąć historię do pierwszej daty z prawdziwymi świecami przed walidacją? To także zmieni wyniki raportu.
6. **ALUMINIUM i COTTON** mają słabe dane także obecnie (dużo świec o zerowym zasięgu, luki). Czy wyłączyć je ze skanowania do czasu znalezienia lepszego źródła?
7. **Binance**: `api.binance.com` jest niedostępne z tej lokalizacji (HTTP 451), dane idą z `data-api.binance.vision`. Z Polski główny host powinien działać; adapter sam wybierze działający. Nic do decyzji, tylko informacja.

### Nowe pytania (C. Newsy)

1. **Sprawdzenie feedów z Twojego komputera.** Uruchom `cfd news check-feeds`. Dziewięć wpisów w `config/feeds.yaml` ma `enabled: false`: Bankier (2) i CNBC odrzucały automat z serwera w chmurze (HTTP 403 z ochrony przed botami), a NBP, PAP Biznes, ESPI/EBI, Bank Anglii, Bank Japonii i SNB były stąd nieosiągalne (adresy z pamięci, niezweryfikowane). Te, które pokażą OK, przełącz na `enabled: true`; błędne adresy popraw albo usuń. Alternatywa: odblokować w środowisku testowym hosty `nbp.pl`, `biznes.pap.pl`, `www.gpw.pl`, `www.bankofengland.co.uk`, `www.boj.or.jp`, `www.snb.ch`, `search.cnbc.com`.
2. **Bankier i CNBC, jeśli u Ciebie też zwrócą 403.** Nie obchodzę zabezpieczeń przed botami. Czy wtedy usunąć te wpisy na stałe i zostać przy Google News PL, czy szukać innego polskiego źródła z RSS (np. Stooq, Money.pl, ISBnews)?
3. **Regulamin Google News RSS.** Feed zawiera zastrzeżenie: użytek osobisty, niekomercyjny, w czytniku RSS. Narzędzie jest prywatne, więc to się mieści, ale to 10 z 18 działających źródeł. Czy akceptujesz to ryzyko, czy ograniczyć liczbę zapytań?
4. **Tłumienie powtórek alertów.** Kolejny news o temacie, który w ostatnich 60 minutach dostał już wagę 3, dostaje teraz 2 (bez alertu). Bez tego odczyt CPI dał 60 alertów w jednym przebiegu. Ryzyko: druga, inna wiadomość na ten sam temat w ciągu godziny (np. decyzja Fed, a 20 minut później zaskakująca wypowiedź Powella) nie wywoła alertu z samych reguł. Zostawić 60 minut, skrócić (np. 20), czy wyłączyć? Parametr `repeat_cooldown_minutes` w `news/pipeline.py`; mogę go wynieść do `config/settings.yaml` (plik poza moim zakresem).
5. **Klucz Anthropic.** Bez `ANTHROPIC_API_KEY` w `.env` nie dało się porównać reguł z LLM. Po wpisaniu klucza: `python -m cfd.news.compare --limit 50`. Szacowany koszt pracy ciągłej to ok. 4 USD miesięcznie (zakres 1–13 USD) na modelu `claude-haiku-5-5`. To źródło płatne (zasada 4): potwierdź, że się zgadzasz.
6. **Zależność `anthropic`.** Klasyfikator LLM używa teraz oficjalnego SDK. Trzeba dopisać go do `pyproject.toml` (np. grupa opcjonalna `llm = ["anthropic>=2.8"]`) i do instrukcji instalacji; nie ruszałem tego pliku. Bez pakietu działają same reguły.
7. **Google News jest wolny.** Mediana opóźnienia 64 minuty, 23% pozycji w ciągu 10 minut; feedy bezpośrednie (MarketWatch, WSJ) 3–8 minut. Czy alerty wagi 3 mają pochodzić także z Google News, czy tylko ze źródeł bezpośrednich, a Google News ma być tłem?

### Nowe pytania (D. Kalendarz makro)

1. **Klucz BLS (darmowy).** Bez klucza BLS daje 25 zapytań na dobę na adres IP; z kluczem 500. Rejestracja: https://data.bls.gov/registrationEngine/ . Jeśli chcesz odczyty CPI/NFP/PPI w minucie publikacji (zamiast ok. 40 minut z FRED), dopisz do `.env` linię `BLS_API_KEY=...` (i do `.env.example` pustą `BLS_API_KEY=` — nie ruszałem tego pliku). Bez klucza wszystko działa, z FRED jako zapasem.
2. **Odczyty spoza USA.** Do sprawdzenia potrzebne odblokowanie hostów: `ec.europa.eu` (Eurostat), `apps.bea.gov` (BEA), ewentualnie `api.ons.gov.uk`, `www.e-stat.go.jp`. Do tego czasu dla EUR/GBP/JPY/CNY zostaje `cfd macro set-actual` i tor newsowy. Czy to wystarczy, czy dopisywać kolejne adaptery?
3. **Reguły łapiące wystąpienia.** `match: "ecb"` i `"fomc"` w `config/macro_rules.yaml` pasują też do „… Speaks”. Zawęzić do decyzji o stopach (np. „Main Refinancing Rate”, „Federal Funds Rate”, „FOMC Statement”)?
4. **Okno alertu po publikacji.** `runner.job_macro` alarmuje tylko o odczytach z ostatnich 6 godzin; stopa Fed z FRED pojawia się następnego dnia. Wydłużyć okno do 24–36 h, czy decyzje o stopach zostawić torowi newsowemu?
5. **Zaokrąglenia.** Odczyt liczony z serii może różnić się o 0.1 od komunikatu urzędu (sprzedaż detaliczna, PCE). Czy dla tych wskaźników wymagać różnicy ≥ 0.2 względem prognozy, zanim pójdzie alert (`surprise_effects` ma parametr `min_rel`, dziś nieużywany)?

### Nowe pytania (E. Fundamenty)

1. **Klucz FRED** (`FRED_API_KEY`): nadal go nie ma. Bias działa bez niego przez publiczny plik `fredgraph.csv`, więc klucz nie jest już warunkiem. Warto go jednak dodać: API jest oficjalną, stabilniejszą drogą, a ścieżka z kluczem nie została dotąd sprawdzona na żywo.
2. **Klucz EIA** (`EIA_API_KEY`, darmowa rejestracja: eia.gov/opendata/register.php): brak. Zapasy pobierane są ze stron historii na www.eia.gov (działa). Po dodaniu klucza trzeba raz uruchomić `cfd bias check` i potwierdzić, że ścieżka API v2 działa, bo powstała bez możliwości sprawdzenia. Do `.env.example` trzeba dopisać `EIA_API_KEY=`.
3. **Neutralne pozycjonowanie COT**: czy ma liczyć się jako 0 w średniej biasu (obecnie tak, rozcieńcza inne składowe), czy być pomijane, gdy percentyl jest między 10 a 90?
4. **Brent w COT**: dla OIL używam kontraktu „BRENT LAST DAY” z NYMEX. Alternatywy: pozycjonowanie z WTI albo brak składowej COT dla OIL. Która wersja?
5. **COT dla indeksów i krypto**: dodać (raport TFF, np. E-mini S&P 500 `13874A`, Nasdaq `209742`, Bitcoin CME `133741`)? Jeśli tak, to którą grupę traktować kontrariańsko: leveraged funds czy asset managers?
6. **E3**: nadal potrzebna lista spółek.

### Nowe pytania (B, F i środowisko)

1. **Walidacja: żadna strategia nie przeszła** (`WYNIKI.md`, B1). Sześć PASS na 1d i jeden na 4h nie przetrwało kontroli
   na drugim interwale. `alert_strategies` zostaje puste. Czy: (a) najpierw naprawić dane (pytania 4 i 5 z sekcji A)
   i powtórzyć raport, (b) od razu projektować nowe strategie i filtr reżimu (G3), (c) jedno i drugie?
2. **Mnożniki lota do `cfd size`.** Plik `config/contracts.yaml` jest pusty. Razem ze specyfikacją kosztów (punkt 1 u góry)
   podaj dla każdego instrumentu „wartość nominalną 1 lota” i walutę; do tego czasu trzeba podawać `--lot-multiplier`.
3. **Wariant uruchamiania.** W `deploy/` są trzy gotowe warianty (systemd, Docker, Windows); żaden nie był uruchomiony
   na docelowym systemie. Po wyborze (punkt 2 u góry) sprawdź pierwszy start i daj znać, co padło.
4. **Hosty niedozwolone w środowisku testowym Claude Code.** Żeby dokończyć weryfikację stąd, trzeba dopisać do środowiska
   „analizator-cfd”: `api.telegram.org`, `nbp.pl`, `biznes.pap.pl`, `www.gpw.pl`, `www.bankofengland.co.uk`, `www.boj.or.jp`,
   `www.snb.ch`, `ec.europa.eu`, `apps.bea.gov`. Limit to 20 hostów na środowisko zakładane przez Claude Code, więc
   część obecnych trzeba by usunąć albo dopisać resztę ręcznie w ustawieniach. Alternatywa: uruchomić te sprawdzenia u siebie.
5. **Stare wpisy w `cfd health`.** Wyłączone feedy (Bankier, CNBC) nadal widnieją jako BŁĄD z wcześniejszych prób.
   Czy `cfd health` ma pokazywać tylko źródła aktywne w konfiguracji?

### Odpowiedzi użytkownika z 2026-11-11 i co z nich wynikło

- **Rolowania: wykluczyć.** Zrobione (`WYNIKI.md`, B1). Korekta wsteczna cen nie była potrzebna.
- **Koszty XTB.** Swapy wpisane z PDF-a. Nadal potrzebne: **spready i wartość nominalna 1 lota** (z walutą).
  Strona specyfikacji XTB odrzuca automat (403), więc potrzebny jest dokument, zrzuty ekranu albo wklejony tekst tabeli.
- **Telegram i alerty: poczekać.** Nic nie zmieniane; `alert_strategies` puste.
- **Nowe pytanie:** symbol AUS200 w konfiguracji a `AU200.cash` w XTB: zmienić nazwę w `instruments.yaml`?

### Nowe pytania (2026-11-12: kierunek „bez bota”, zbieranie w przód, spółki)

1. **Repozytorium jest publiczne** i zawiera listę Twoich spółek (decyzja 17 nadal otwarta). Zostawić publiczne
   (Actions bez limitu minut), czy zmienić na prywatne (wtedy skan co 30 minut przekroczy darmową pulę i trzeba go rozrzedzić)?
2. **Ekran na telefonie.** Najprostsza droga to GitHub Pages: Settings → Pages → Source „GitHub Actions” oraz zmienna
   `PUBLIKUJ_STRONE=tak`. Strona będzie publiczna. Alternatywa: pobierać artefakt `stan-na-teraz` z przebiegu albo wrócić do panelu
   z logowaniem (Supabase + Vercel). Którą drogę wybierasz?
3. **Tor szybki (funkcje Supabase, kod TypeScript, Telegram).** Po rezygnacji z bota jest zbędny. Usunąć z repozytorium, czy zostawić?
4. **`SPL.PL`**: Yahoo nie ma symbolu `SPL.WA` (spółka to dziś Erste Bank Polska). Jaki ma ticker w XTB i na GPW?
5. **Progi listy kontrolnej spółek** są podręcznikowe i niewalidowane. Chcesz inne progi albo inne filary (np. dywidenda, przepływy pieniężne)?
6. **Spready i wartość lota z xStation**: nadal brak; od nich zależy, czy wyniki „blisko zera” (wybicia na akcjach 1d) są dodatnie.

### Odpowiedzi użytkownika z 2026-11-12

- **Bez bota.** Program ma pokazywać stan po otwarciu, bez alertów. **Tor szybki usunięty** (pytanie 3 powyżej: „usuń”):
  `supabase/functions/`, `supabase/tests/`, `supabase/cron.sql.template`, wysyłka na Telegram, `cfd export-config`,
  testy Deno w Actions. Decyzje 3, 10 i 11 z tabeli (Telegram, próg alertów, cisza nocna) są przez to bezprzedmiotowe.
- **Kolejność prac:** najpierw zbieranie newsów i makro w przód, potem fundamenty spółek. Oba zrobione.
- **Nadal otwarte:** repozytorium publiczne czy prywatne, sposób udostępnienia ekranu na telefonie, ticker `SPL.PL`,
  spready i wartość lota z xStation, oraz co zrobić z pozostałością po v0.3 (`supabase/migrations/`, `src/cfd/sync.py`, `web/`, `vercel.json`).
- **Specyfikacja XTB (PDF z 2026-11-12).** Mnożniki lota wpisane; spready są zmienne i nie ma ich w dokumencie.
  Wniosek z analizy przed kosztami: brak spreadów nie zmienia oceny strategii (`WYNIKI.md`). Pytanie o spready z listy powyżej jest zamknięte.

