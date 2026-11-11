## C1. Feedy

**Co zrobione.** `cfd news check-feeds` na żywo (10–11.11.2026, środowisko w chmurze za proxy z listą hostów), ręczne sprawdzenie nagłówków odpowiedzi, poprawki `config/feeds.yaml` i adaptera `src/cfd/news/rss.py`.

**Wynik (stan końcowy: działa 18 z 18 włączonych; 9 wpisów wyłączonych czeka na sprawdzenie u użytkownika).**

| Status | Feedy |
|---|---|
| działa | `fed_press`, `ecb_press`, `eia_today`, `eia_press`, `marketwatch`, `coindesk`, nowy `wsj_markets` (Dow Jones, 61 pozycji), 8 zapytań Google News EN, 2 nowe zapytania Google News PL (`NBP stopy procentowe`, `GPW WIG20`) |
| serwis odrzuca automat | `bankier_news`, `bankier_gielda` (HTTP 403, nagłówek `cf-mitigated: challenge`, czyli wyzwanie Cloudflare; także dla `robots.txt`), `cnbc_top` (HTTP 403 „Access Denied” z Akamai). Sprawdzone z adresu IP centrum danych; z domowego łącza mogą działać. Ustawione `enabled: false`, zabezpieczeń nie obchodzę (zasada 3). |
| serwis zmienił adres | `coindesk`: adres z końcowym `/` odpowiadał 308; poprawiony na `…/outboundfeeds/rss`. |
| niesprawdzalne tutaj (host zablokowany przez proxy środowiska) | nowe wpisy `nbp_news`, `pap_biznes`, `pap_espi`, `boe_news`, `boj_news`, `snb_press`: adresy z pamięci, nigdy niepobrane, `enabled: false`, komentarz „niezweryfikowane (host zablokowany w srodowisku testowym)”. |
| odrzucone | `mw_marketpulse` (Dow Jones) odpowiada 200, ale najnowsza pozycja jest z lipca 2025: martwy feed, nie dodany. |

**Hosty do odblokowania, żeby dokończyć weryfikację:** `nbp.pl`, `biznes.pap.pl`, `www.gpw.pl`, `www.bankofengland.co.uk`, `www.boj.or.jp`, `www.snb.ch`, `search.cnbc.com` (alternatywny adres RSS CNBC). Prościej: uruchomić `cfd news check-feeds` z własnego komputera; polecenie sprawdza teraz także wyłączone wpisy i oznacza je `[wylaczony w feeds.yaml]`.

**Google News.**
- Przekierowanie 302 pojawia się tylko wtedy, gdy w adresie brakuje kompletu `hl`, `gl`, `ceid` (Google dokleja domyślne). Adapter zawsze je wysyła i dostaje 200 od razu; gdyby 302 jednak przyszło, klient `httpx` ma `follow_redirects=True` (test na atrapie transportu).
- Blokada: łącznie ok. 20 przebiegów po 8–10 zapytań, w tym 14 kolejnych co ok. 4 minuty przez 54 minuty (20:42–21:37 UTC): 0 błędów, 0 odpowiedzi 429, 0 przekierowań na stronę `/sorry/`, czas przebiegu stały 10–11 s. Przy odstępie 5 minut Google nie blokuje. Nie testowałem dłużej niż godzinę ani z domowego adresu IP.
- Dodany parametr `when: "1d"`: bez niego wyszukiwarka zwraca też artykuły sprzed tygodni.
- Feed zawiera zastrzeżenie Google: użytek osobisty, niekomercyjny, w czytniku RSS (patrz pytanie w decyzjach).

**Zmienione w kodzie.**
- `rss.py`: pole `enabled` we wpisie feedu; zapytanie Google News jako napis albo słownik `{q, hl, gl, ceid}` (polska edycja); `when`; `fetch_feed` zgłasza `DataSourceError` z przyczyną (HTTP 403 z ochrony przed botami, 429, strona blokady Google, odpowiedź niebędąca XML, feed bez pozycji) zamiast surowego wyjątku albo cichej pustej listy.
- `rss.py`: Google News dokleja do tytułu „ - Wydawca”, a opis to powtórzony tytuł. Wydawca jest teraz odcinany, opis pomijany. W próbce 599 newsów 13 dostało symbol albo wagę wyłącznie przez nazwę wydawcy („Crude Oil Prices Today | OilPrice.com”, „Crypto News”).
- `cli.py` (`news check-feeds`): sprawdza także wyłączone wpisy, krótszy komunikat błędu.
- Fixtures z prawdziwych odpowiedzi: `tests/fixtures/news_gnews_gold_price.xml`, `news_gnews_pl_nbp.xml`, `news_fed_press.xml`.

**Co nie działa.** Polskie źródła bezpośrednie (Bankier, PAP Biznes, ESPI/EBI, NBP) nie są potwierdzone: Bankier odrzuca automat, reszta niesprawdzalna stąd. Do tego czasu Polskę pokrywają tylko dwa zapytania Google News PL (10 i 17 pozycji na dobę).

## C2. Jakość mapowania i klasyfikacji

**Co zrobione.** Trzy serie `cfd news poll` (10.11.2026, dzień publikacji CPI w USA): 2 przebiegi o 07:40 UTC, 4 przebiegi 15:42–15:52 i 14 przebiegów co ok. 4 minuty 20:42–21:37 (ostatnia seria już na nowej konfiguracji i nowym kodzie). W bazie 1067 newsów. Próba bazowa do oceny starych reguł: 599 newsów z dwóch pierwszych serii (408 zmapowanych; wagi: 85 × 3, 212 × 2, 97 × 1, 16 duplikatów).

**Fałszywe trafienia słów kluczowych (próba bazowa, liczone po całych słowach).**

| Słowo | Trafień | Wynik |
|---|---|---|
| `fed` | 53 | 0 fałszywych (wszystkie „Fed”). Zawężone do pisowni `Fed`/`FOMC`, bo „fed up”, „fed cattle” przeszłyby. |
| `gold` | 84 | ok. 30 nie dotyczy XAU/USD: ceny detaliczne w Indiach, Pakistanie, Indonezji, Wietnamie (ok. 15), spółki wydobywcze: Kinross, Barrick, Equinox, „gold miners” (ok. 12), pozostałe. Dodana lista wykluczeń; odcina 24 z 84. |
| `eth`, `ether` | 2 + 1 | 0 fałszywych; zawężone do pisowni `ETH`, `Ether`. |
| `lng` | 2 | 1 fałszywe („LNG Traffic Through Hormuz”: nie Henry Hub). Zastąpione przez `lng exports`, `us lng`. |
| `wall street` | 8 | 5 to „co mówi Wall Street” (analitycy), nie indeks. Przeniesione z US500 wprost do tematu `us_stocks`. |
| `soybean` | 1 | 1 fałszywe („Soybean Oil”); wykluczenie. |
| `inflation` (temat USA) | 88 | łapało inflację spoza USA (Grecja, Indie). Zawężone do `CPI`, `us inflation`, `inflation report/data`, `PCE`. |
| `surge`, `plunge`, `crash`, `record high` | 9 + 5 + 3 + 4 | ok. połowa dotyczy czegoś innego niż instrument (rentowności, auta, emisje CO2, pojedyncze akcje). Liczą się teraz tylko razem z dopasowaniem wprost. |
| `bankruptcy`, `default`, `emergency`, `halts` | 1 | 1 fałszywe („Global Bankruptcy Fears”). Zawężone do fraz („files for bankruptcy”, „debt default”, „emergency meeting”, „trading halted”). |
| `corn`, `sugar`, `boj`, `gpw`, `cotton`, `coffee` | 0 | brak trafień tego dnia, więc brak pomiaru. Zawężone zapobiegawczo do fraz rynkowych („corn futures”, „sugar prices”) i pisowni skrótów (`BoJ`, `GPW`); testy na przykładach („blood sugar”, „corn dogs”, „bój”). |

**Ręczna ocena 50 newsów z wagą 3 (stare reguły, pierwsze 50 w kolejności pobrania).**
- 22 z 50 (44%) opisywały faktyczne, świeże zdarzenie rynkowe (odczyt CPI, Waller o podwyżce o 0,5 pkt, Nagel z EBC, spadek ropy po słowach Trumpa o Iranie, produkcja OPEC).
- Z tych 22 tylko 5 to pierwsza informacja o zdarzeniu; 17 to kolejne redakcje piszące o tym samym. Użyteczny alert: 5 z 50 (10%).
- 22 z 50 (44%) to zapowiedzi, prognozy i komentarze („ahead of CPI”, „Price Forecast”, „What to expect”), podbite do 3 przez samo słowo „CPI”.
- 6 z 50 (12%) to szum (podsumowania wczorajszej sesji, „Global Bankruptcy”).
- Skutek praktyczny: jeden przebieg o 15:42 wysłałby 60 alertów.

**Zmiany w regułach i ich efekt.**
- Frazy wysokiej wagi szukane tylko w tytule; słowa ruchu (`surge`, `plunge`…) tylko przy dopasowaniu wprost.
- Tytuł będący zapowiedzią, prognozą albo pytaniem dostaje najwyżej 2.
- Kolejny news o temacie, który w ostatnich 60 minutach dostał już wagę 3 (te same frazy + ten sam instrument), dostaje 2 (`repeat_cooldown_minutes` w `process_items`).
- Te same 599 newsów przeliczone nowymi regułami: waga 3 dla 16 zamiast 85; z ocenionych 50 zostaje 10. Uwaga: w tym przeliczeniu okno 60 minut objęło całą próbę naraz, więc efekt tłumienia powtórek jest zawyżony.
- Na żywo, nowa konfiguracja: przebieg nadrabiający 5 godzin dał 12 alertów (wcześniej 60 w podobnej sytuacji), potem 13 przebiegów ciągłych przez 54 minuty dało 2 alerty na 106 nowych newsów.
- Reguły nadal nie rozumieją treści: wśród 16 pozostałych „trójek” ok. połowa jest trafna. Resztę ma odsiać LLM (C3).

**Opóźnienie publikacja → pobranie** (newsy, które pojawiły się między kolejnymi przebiegami co ok. 4 minuty; 127 pozycji):

| Źródło | n | mediana | p25 | p90 | do 10 min |
|---|---|---|---|---|---|
| MarketWatch | 6 | 4,5 min | 3,1 | 6,4 | 6 z 6 |
| WSJ Markets | 6 | 4,8 min | 3,3 | 7,7 | 6 z 6 |
| Google News | 115 | 64 min | 11,9 | 368 | 26 z 115 (23%) |

- Feedy bezpośrednie: opóźnienie równe odstępowi odpytywania plus 1–3 minuty; przy `poll_seconds: 120` realnie 2–5 minut.
- Google News: wolny i nierówny. Jedna trzecia pozycji (38 z 115) pojawia się w wynikach ponad 3 godziny po publikacji. Nadaje się na tło i potwierdzenie, nie na szybki alert.
- Fed, EBC, EIA i CoinDesk nie opublikowały nic nowego w oknach pomiaru, więc brak dla nich liczby.

**Co nie działa / ograniczenia.** Jeden dzień danych, zdominowany przez CPI; słowa rolne i polskie praktycznie bez próby. Nagłówki PL trafiają do W20 tylko przez temat `nbp` (waga 1), bo frazy wysokiej wagi po polsku są nieliczne („podwyżka stóp”, „stopy bez zmian”…).

## C3. Klasyfikator LLM

**Część porównawcza na żywo: niewykonana.** W środowisku nie ma `ANTHROPIC_API_KEY`, więc porównania reguły vs LLM na 50 newsach nie było. Przygotowany skrypt robi to jednym poleceniem po wpisaniu klucza: `python -m cfd.news.compare --limit 50 --min-importance 3` (tabela, zgodność wag, tokeny, koszt).

**Model i wywołanie (źródło: skill `claude-api`, stan 2026-11-03).**
- Tani model to Claude Haiku 5.5, identyfikator `claude-haiku-5-5` (bez sufiksu daty). Domyślna wartość w kodzie i `.env.example` była poprawna.
- Cena: 0,10 USD za 1 mln tokenów wejścia, 0,50 USD za 1 mln tokenów wyjścia (prompty do 100 tys. tokenów). Haiku 4.5 kosztuje 1 / 5 USD.
- Błąd w starym wywołaniu: `max_tokens: 300` przy modelu, który domyślnie „myśli”, a myślenie wlicza się do limitu. Odpowiedź mogła urwać się przed JSON-em i każdy news wracałby po cichu do reguł. Odpowiedź może też zaczynać się od bloku `thinking`.
- Poprawione w `src/cfd/news/classify.py`: oficjalne SDK `anthropic` zamiast ręcznego `httpx`; `max_tokens: 1024`; `output_config: {effort: "low", format: {type: "json_schema", …}}` (gwarantowany JSON zgodny ze schematem zamiast wycinania klamer z tekstu); bloki czytane po typie; `stop_reason` `refusal` i `max_tokens` oznaczają powrót do reguł; zliczanie tokenów i kosztu. Bez `temperature` i bez ręcznego budżetu myślenia (na tym modelu dają błąd 400).
- Kierunki w odpowiedzi to teraz lista `{symbol, direction: up|down|none}`; parser przyjmuje też stary format słownikowy.
- Sprawdzone lokalnie: SDK `anthropic` 2.8.0 przyjmuje parametr `output_config`. Prawdziwego wywołania API nie było.

**Testy na atrapie.** `test_llm_classifier_request_shape_and_response_parsing` (kształt żądania: model, `max_tokens`, `output_config`, brak usuniętych parametrów; odpowiedź z blokiem `thinking` przed tekstem; zliczanie tokenów i kosztu) oraz `test_llm_classifier_falls_back_on_refusal_truncation_and_errors`.

**Szacunek kosztu miesięcznego (szacunek, nie pomiar).**
- Wolumen newsów z wagą regułową ≥ 2, czyli trafiających do LLM: 45 w 54 minuty ciągłego odpytywania wieczorem (ok. 50 na godzinę); 164 z jednego przebiegu po 8 godzinach przerwy (ok. 20 na godzinę, zaniżone, bo feed pokazuje tylko 100 najnowszych pozycji). Przyjmuję 20–50 na godzinę w dni robocze, średnio ok. 800 dziennie, w weekendy ok. 250: razem ok. 20 tys. wywołań miesięcznie. To był dzień CPI, więc raczej górna część zakresu.
- Tokeny na wywołanie (z długości promptu: 651 znaków plus schemat 442 znaki): ok. 500 wejścia i ok. 300 wyjścia łącznie z myśleniem przy `effort: low`.
- Koszt jednego wywołania: 500 × 0,10 / 1 mln + 300 × 0,50 / 1 mln ≈ 0,0002 USD.
- **Miesięcznie ok. 4 USD** (20 tys. × 0,0002). Zakres przy skrajnych założeniach (10–36 tys. wywołań, 0,00012–0,00035 USD każde): 1–13 USD. Na Haiku 4.5 byłoby to ok. 10 razy więcej.
- Po pierwszym uruchomieniu z kluczem `compare` wypisze rzeczywiste tokeny na news; wtedy szacunek warto poprawić.

**Co nie działa / do zrobienia.**
- Pakiet `anthropic` nie jest zadeklarowany w `pyproject.toml` (plik poza moim zakresem). Bez niego klasyfikator LLM loguje ostrzeżenie i wraca do reguł. Trzeba dopisać zależność, np. `llm = ["anthropic>=2.8"]` w `[project.optional-dependencies]`.
- Host `api.anthropic.com` trzeba dopuścić tam, gdzie narzędzie będzie działać.
