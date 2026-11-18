# Rejestr hipotez („lekcje” silnika)

Silnik nie uczy się sam. Zmiany w strategiach wprowadza Claude Code w sesjach uruchamianych **ręcznie przez użytkownika**
(decyzja z 2026-11-15: kontrola zużycia tokenów). Ten plik jest pamięcią między sesjami: każda sesja zaczyna od zera.

## Jak poprosić o sesję

Wystarczy napisać: „sesja nauki”. Claude Code wykonuje wtedy procedurę poniżej i kończy raportem.

## Procedura sesji

1. `git pull`, przeczytaj ten plik i `walidacja/` (ostatnie przeliczenie). Dziennik: `git fetch origin dane` i `git show origin/dane:sygnaly.csv`
   (skan co godzinę nadpisuje tę gałąź eksportem dziennika; artefaktów Actions nie da się pobrać ze środowiska Claude Code).
2. **Najpierw rozlicz stare hipotezy**: dla każdej w stanie „czeka na dziennik” sprawdź sygnały zebrane PO dacie jej zapisania.
3. Postaw najwyżej **dwie** nowe hipotezy. Zapisz je w tabeli **przed** uruchomieniem testu, z uzasadnieniem i kryterium.
4. Przetestuj na historii metodą zakrytej przyszłości (`cfd context-test`, `cfd report` albo osobny skrypt). Wpisz wynik, także negatywny.
5. Hipoteza, która przeszła historię, dostaje stan „czeka na dziennik”. Do silnika (ekran, wyróżnienie sygnału) trafia dopiero po
   potwierdzeniu na sygnałach z dziennika zebranych po jej zapisaniu.
6. Commit z opisem lekcji, wpis do `WYNIKI.md`, krótki raport dla użytkownika.

## Reguły, których nie wolno łamać

- Hipoteza zapisana **przed** testem. Żadnego dopisywania po fakcie tego, co „wyszło”.
- Najwyżej dwie nowe hipotezy na sesję. Licznik wszystkich prób jest jawny (tabela poniżej): im więcej prób, tym więcej trafień z przypadku.
- Historia tylko odsiewa. **Ostatecznym sędzią jest dziennik**: sygnały zebrane po zapisaniu hipotezy.
- Kryterium potwierdzenia w dzienniku: co najmniej 50 rozliczonych sygnałów, dodatni średni wynik po kosztach, t ≥ 1,65.
- Nie poluzowuj progów walidacji i nie dopisuj nic do `alert_strategies` (zasady 7 i 8 z `CLAUDE.md`).
- Odrzuconych hipotez nie usuwaj z tabeli.

## Stan wiedzy na start (2026-11-15)

- Trzy strategie techniczne nie mają przewagi po kosztach na żadnym interwale (walk-forward, 71 instrumentów).
- Filtry kontekstowe (reżim, trend dzienny, zmienność, sesja, VIX, bias fundamentalny): 0 potwierdzonych na 276.
- Przed kosztami jest mała przewaga strategii podążających za trendem na 1d (+0,06 do +0,09 R), słabnąca po 2016 r.;
  na CFD zjada ją swap. Na 1h wynik przed kosztami jest zerowy.
- Najlepszy trop: wybicia (`donchian_breakout`) na akcjach na 1d, bez swapu: +0,11 R przed kosztami, za słabe statystycznie.
- Newsów i kalendarza makro nie da się ocenić wstecz; kontekst jest zapisywany przy sygnałach od 2026-11-12.

## Rejestr

Stany: `zapisana` → `odrzucona na historii` / `czeka na dziennik` → `potwierdzona` / `odrzucona w dzienniku`.

| Nr | Data zapisania | Hipoteza i uzasadnienie | Kryterium na historii | Wynik na historii | Stan | Wynik w dzienniku |
|---|---|---|---|---|---|---|
| H1 | 2026-11-16 | **Wybicia na akcjach tylko w stronę LONG.** `donchian_breakout`, akcje, 1d, tylko sygnały kupna. Uzasadnienie: akcje mają dodatni dryf, więc wybicia w dół są w nich słabsze niż w górę; akcje nie mają swapu; użytkownik i tak nie gra krótko na posiadanych spółkach (decyzja 19). Zagrożenie znane z góry: lista 30 spółek to spółki, które użytkownik dziś posiada (dobór po fakcie), co zawyża wyniki LONG. | Próba odkrywcza (starsze 60% transakcji): ≥ 200 transakcji, średnio > 0 R po kosztach, t ≥ 2. Próba potwierdzająca (nowsze 40%): ≥ 100 transakcji, średnio > 0 R, t ≥ 1,65. Kontrola doboru: ten sam wariant na 18 indeksach liczony przed kosztami (odpowiednik ETF bez swapu) musi mieć średnio > 0 R na próbie potwierdzającej; inaczej wynik uznaję za efekt doboru spółek. | Odkrywcza (do 2019-03-30): 589 transakcji, +0,183 R, t = 2,21 (spełnione). Potwierdzająca: 393 transakcje, +0,118 R, **t = 1,10 (niespełnione, próg 1,65)**. Kontrola na indeksach: +0,063 R przed kosztami (spełniona, ale t = 0,87). Dodatkowo: 75% całego zysku pochodzi z 3 spółek (OXIG.UK, RBW.PL, OXB.UK); bez nich +0,051 R, t = 0,72. | odrzucona na historii | – |
| H2 | 2026-11-16 | **H1 tylko przy rosnącym szerokim rynku.** Jak H1, ale sygnał liczy się tylko wtedy, gdy US500 zamknął poprzednią sesję powyżej swojej średniej z 200 sesji. Uzasadnienie: wybicia pojedynczych spółek częściej się utrzymują, gdy cały rynek rośnie (klasyczny filtr trendu rynku). | Te same progi co H1, a dodatkowo średni wynik na próbie potwierdzającej wyższy niż w H1 (inaczej filtr nic nie wnosi). | Odkrywcza (do 2019-09-30): 471 transakcji, +0,056 R, **t = 0,59 (niespełnione)**. Potwierdzająca: 314 transakcji, +0,178 R, t = 1,88: dobry wynik tylko w nowszej połowie to wzorzec przypadku, nie potwierdzenie. Przy tej samej granicy co H1 filtr daje +0,125 R wobec +0,118 R, czyli nic nie wnosi. | odrzucona na historii | – |
| H3 | 2026-11-16 | **Trend miesięczny (tylko LONG albo gotówka).** Na koniec każdego miesiąca instrument jest „w trendzie”, gdy co najmniej dwie z trzech stóp zwrotu (3, 6 i 12 miesięcy) są dodatnie. Portfel: równe wagi we wszystkich instrumentach w trendzie, reszta w gotówce; zmiana raz w miesiącu. Uzasadnienie: jedyna przewaga przed kosztami w dotychczasowych testach to podążanie za trendem na 1d, a w literaturze trend jest najlepiej udokumentowany na horyzoncie 1–12 miesięcy; rzadkie transakcje ograniczają koszty. Parametry ustalone z góry, bez strojenia. Zakres: indeksy (bez VIX), akcje, metale szlachetne, krypto. **Surowce wyłączone**, bo miesięczne stopy zwrotu z kontraktów ciągłych bez korekty rolowania są zafałszowane. Liczone jak dla akcji i ETF-ów: spread przy każdej zmianie składu, bez swapu. | Miesięczne stopy portfela po kosztach, podział w czasie 60/40. Odkrywcza: średnia > 0, t ≥ 2. Potwierdzająca: średnia > 0, t ≥ 1,65 **oraz** wskaźnik Sharpe'a wyższy niż dla portfela „kup i trzymaj wszystko” na tym samym zakresie (inaczej trend nic nie wnosi ponad samo posiadanie). Kontrola doboru: to samo musi zachodzić na próbie potwierdzającej bez akcji (lista spółek jest dobrana po fakcie). | Odkrywcza (437 miesięcy do 2002-06): +0,51%/mies., t = 3,61 (spełnione). Potwierdzająca (292 miesiące od 2002-07): +0,99%/mies., t = 6,29, Sharpe 1,28 wobec 0,96 dla „kup i trzymaj” (spełnione). Bez akcji: +0,57%/mies., t = 4,02, Sharpe 0,82 wobec 0,65 (spełnione). Uwaga: trend daje **niższą** stopę zwrotu niż „kup i trzymaj” (0,99% wobec 1,36%), a lepszy Sharpe bierze się z mniejszych obsunięć (−13% wobec −52%). | **czeka na dziennik** | ocena w przód: `cfd monthly-test --since 2026-12` |
| H4 | 2026-11-16 | **Siła względna.** Na koniec każdego miesiąca instrumenty z tego samego zakresu co H3 są szeregowane według stopy zwrotu z 6 miesięcy; portfel trzyma górną jedną trzecią w równych wagach przez kolejny miesiąc. Uzasadnienie: „które będą lepsze od reszty” jest łatwiejszym pytaniem niż „wzrośnie czy spadnie”; siła względna jest jednym z najlepiej udokumentowanych efektów. Okno 6 miesięcy i jedna trzecia ustalone z góry. | Różnica miesięcznych stóp: górna jedna trzecia minus średnia całego zakresu, po kosztach spreadu od obrotu. Odkrywcza: średnia różnica > 0, t ≥ 2. Potwierdzająca: średnia różnica > 0, t ≥ 1,65. Kontrola doboru: to samo na próbie potwierdzającej bez akcji. | Odkrywcza (272 miesiące): +0,57%/mies., t = 2,64 (spełnione). Potwierdzająca (182 miesiące od 2011-09): +0,42%/mies., **t = 1,58 (niespełnione, próg 1,65)**. Bez akcji: +0,21%/mies., t = 0,90 (niespełnione): efekt opiera się na spółkach dobranych po fakcie. | odrzucona na historii | – |
| H5 | 2026-11-17 | **Model przewidywań kierunku (regresja logistyczna).** Jeden model wspólny dla zakresu H3 (indeksy bez VIX, akcje, metale szlachetne, krypto; surowce wyłączone z powodu rolowań), osobno dla h = 5 i h = 20 sesji. Cechy na zamknięciu dnia t (tylko dane do t): log-stopy zwrotu 5/20/60/120/250 sesji, zmienność 20/60, odległość od SMA50 i SMA200 w ATR14, RSI14, ADX14, głosy trendu 3/6/12 mies. (63/126/252 sesje, jak H3), stopa zwrotu względem US500 z 20 i 60 sesji, pozycja w zakresie 252 sesji, kategoria (one-hot). Cel: 1, gdy zamknięcie w t+h > zamknięcie w t. Regresja logistyczna z karą L2; standaryzacja i siła kary liczone tylko na danych treningowych (siatka C ∈ {0,01; 0,1; 1; 10} wybierana na zbiorze walidacyjnym). Uzasadnienie: pojedyncze reguły techniczne nie mają przewagi, ale trend miesięczny ma (H3); model sprawdza, czy łączenie cech daje lepiej skalibrowane prawdopodobieństwo kierunku niż sama częstość wzrostów. Parametry ustalone z góry. | Podział chronologiczny po datach: trening 65%, walidacja 15%, test 20% (najnowsze daty, użyte raz, na końcu); między zbiorami oczyszczanie h sesji i embargo h sesji. Poziom bazowy: częstość wzrostów per instrument z danych treningowych. Dla każdego h osobno: na teście Brier modelu < Brier bazy, p < 0,025 (0,05 z poprawką Bonferroniego na dwa horyzonty) z bootstrapu blokowego dziennych różnic straty (blok 2h, min. 20 sesji, 2000 losowań), **oraz** log loss modelu niższy niż bazy. Kontrole (warunek ważności): walk-forward (5 okien, oczyszczanie i embargo h) ze średnim Brier skill > 0; model uczony na przetasowanych celach ma skill ≈ 0 (≤ 0,002). | Dane 2000-12 – 2026-11, 52 instrumenty, 240 tys. wierszy; test od 2022-08 (ok. 53,5 tys. wierszy na horyzont), C = 0,01 wybrane na walidacji. **h = 5:** Brier 0,2487 wobec 0,2496 bazy (BSS +0,0037), log loss lepszy o 0,0021, AUC 0,534 (baza 0,535), **p = 0,71 (niespełnione)**; walk-forward średni BSS −0,0026 (niespełnione), przeciek +0,0006 (OK). **h = 20:** Brier 0,2466 wobec 0,2479 (BSS +0,0054), log loss lepszy o 0,0028, AUC 0,533 (baza 0,539), **p = 0,52 (niespełnione)**; walk-forward +0,0042, ale z jednym oknem zawyżonym przez bazę 0/1 dla krótko notowanego instrumentu; test przecieku **+0,0032 (niespełnione)**: model na przetasowanych celach ma prawie tyle samo „skilla” co prawdziwy, czyli przewaga pochodzi z wyrazu wolnego i kategorii (bazy per instrument gorszej od średniej), nie z cech. Model ma AUC nie wyższe niż sama baza per instrument: cechy nie porządkują dni lepiej niż częstość wzrostów. | odrzucona na historii | prognozy i tak są liczone z oznaczeniem jakości „brak”; dziennik `walidacja/prognozy_log.csv`, ocena `cfd model score` |
| H6 | 2026-11-18 | **Wybicia 1d bez strony SHORT.** `donchian_breakout` na 1d: sygnały sprzedaży mają ujemną wartość oczekiwaną, więc ich pominięcie poprawia wynik. Pochodzi z obserwacji ubocznej sesji 1, więc historia jest już „zużyta”: **ocena wyłącznie w dzienniku**, na sygnałach powstałych od 2026-11-18. | (brak testu na historii — dane już widziane) | – | **czeka na dziennik** | Kryterium: ≥ 50 rozliczonych sygnałów `donchian_breakout` 1d SHORT od 2026-11-18, średni wynik < 0 R i t ≤ −1,65 (jednostronnie), oraz średni wynik sygnałów LONG z tego samego okresu wyższy niż SHORT. |
| H7 | 2026-11-18 | **Dryf po wynikach kwartalnych (PEAD).** Spółki, które pokazały zysk na akcję powyżej konsensusu, przez kolejne ~20 sesji zachowują się lepiej niż te poniżej konsensusu. Uzasadnienie: jeden z najlepiej udokumentowanych efektów (rynek reaguje na niespodziankę z opóźnieniem); akcje bez swapu. Definicja: zdarzenia z Yahoo (`get_earnings_dates`: data, EPS prognoza i rzeczywisty, niespodzianka w %), spółki z `instruments.yaml`. Wejście na zamknięciu **drugiej** sesji od daty publikacji (bez zaglądania w przyszłość niezależnie od godziny publikacji), wyjście po 20 sesjach. Wynik: stopa spółki minus stopa indeksu (US500 dla spółek zagranicznych, W20 dla GPW). | Podział zdarzeń w czasie 60/40. Odkrywcza: średnia różnica (niespodzianka dodatnia minus ujemna) > 0, t ≥ 2 (test Welcha). Potwierdzająca: różnica > 0, t ≥ 1,65 **oraz** średnia nadwyżka grupy z dodatnią niespodzianką > 0,3% (koszt wejścia i wyjścia), bo grać da się tylko długą stronę. Zastrzeżenie znane z góry: lista spółek dobrana po fakcie (posiadane + WIG20); różnica grup jest na to mniej wrażliwa niż sam poziom. | **Nie przetestowana: brak danych.** Historia publikacji z prognozami EPS jest w Yahoo tylko na stronie finance.yahoo.com (yfinance ją przegląda jak stronę WWW); ten host jest zablokowany w środowisku, a jego przeglądanie byłoby scrapingiem, którego zgodności z regulaminem nie sprawdziłem. Darmowe API (Yahoo quoteSummary, Nasdaq) dają tylko 4 ostatnie kwartały. | wstrzymana (dane). **2026-11-18, na prośbę użytkownika sprawdzono robots.txt finance.yahoo.com:** dla agentów AI (`anthropic-ai`, `ClaudeBot`, `Claude-Web` i in.) jest `Disallow: /`, więc Claude Code nie pobiera stamtąd danych. Pobieranie przez yfinance z komputera użytkownika (użytek osobisty) jest decyzją użytkownika co do regulaminu Yahoo; po dostarczeniu takiego pliku test można wykonać. | – |
| H8 | 2026-11-18 | **Dryf po reakcji na wyniki (wariant H7 bez prognoz analityków).** Niespodziankę mierzy reakcja ceny: nadwyżkowa stopa spółki nad S&P 500 (US500) w oknie od zamknięcia sesji przed publikacją do zamknięcia drugiej sesji od publikacji („reakcja”). Hipoteza: po dodatniej reakcji przez kolejne 20 sesji spółka zachowuje się lepiej niż po ujemnej. Daty publikacji: SEC EDGAR, formularze 8-K z punktem 2.02 („Results of Operations”); sesja publikacji = data przyjęcia, a gdy przyjęto po 16:00 czasu nowojorskiego, następna sesja. Wejście na zamknięciu drugiej sesji od publikacji (reakcja jest już znana), wyjście 20 sesji później, wynik jako nadwyżka nad US500. Zakres celowo **niezależny od portfela użytkownika**: 30 obecnych spółek Dow Jones + spółki z USA z `instruments.yaml` składające 8-K (ARM składa 6-K, więc odpada). | Podział zdarzeń w czasie 60/40. Odkrywcza: średnia różnica dryfu (reakcja dodatnia minus ujemna) > 0, t ≥ 2 (Welch). Potwierdzająca: różnica > 0, t ≥ 1,65 **oraz** średnia nadwyżka grupy z dodatnią reakcją > 0,3% (koszt). Zastrzeżenia znane z góry: obecny skład Dow Jones to spółki, które przetrwały (błąd przetrwania); duże, płynne spółki to miejsce, gdzie efekt jest w literaturze najsłabszy. | 1053 publikacje, 37 spółek, 2013–2026 (ARM bez 8-K). Odkrywcza (do 2023-10): różnica −0,75 pp, t = −1,25 (**niespełnione**, znak przeciwny). Potwierdzająca: −0,55 pp, t = −0,71; dryf po dodatniej reakcji −0,53%. Sam Dow 30: +0,17 pp (t = 0,32) i −0,11 pp (t = −0,15). Dane zdarzeń: `walidacja/h8_zdarzenia.csv`. | odrzucona na historii | – |

Liczba hipotez przetestowanych do tej pory: **8** (nie licząc 276 filtrów z testu kontekstowego i 639 kombinacji strategii z walidacji).

## Dziennik sesji

### Sesja 1 (2026-11-16)

- **Stare hipotezy do rozliczenia:** brak.
- **Dziennik:** niedostępny w tej sesji. Baza jest w artefakcie `stan-na-teraz`, ale host z plikami artefaktów GitHuba jest zablokowany
  w środowisku Claude Code. I tak nie byłoby czego oceniać: skan zbiera sygnały od 4 dni.
- **Dane do testu:** 31 011 transakcji z okien testowych walk-forward (`reports/kontekst_transakcje.parquet`, stan z 2026-11-12).
  Podział 60/40 w czasie liczony na transakcjach badanego wariantu.
- **Wynik:** H1 i H2 odrzucone na historii (tabela wyżej). Silnik bez zmian.
- **Obserwacja uboczna, NIE lekcja** (zauważona po teście, więc nie wolno jej przyjąć): sygnały SHORT z `donchian_breakout` na 1d tracą
  w nowszej połowie danych zarówno na akcjach (260 transakcji, −0,189 R, t = −2,15), jak i na indeksach przed kosztami
  (317 transakcji, −0,280 R, t = −3,65). Kandydat na hipotezę w następnej sesji: „`donchian_breakout` 1d bez strony SHORT na akcjach i indeksach”.
  Trzeba ją wtedy zapisać i ocenić na danych, których ta obserwacja nie widziała, czyli w dzienniku.
- **Uwaga o H1:** kierunek jest zgodny z oczekiwaniem (LONG dodatni, SHORT ujemny), ale siła nie przechodzi progu, a wynik opiera się
  na trzech spółkach z listy dobranej po fakcie. To dokładnie ten przypadek, przed którym chroni próg.

### Sesja 2 (2026-11-16)

- **Stare hipotezy do rozliczenia:** brak (H1 i H2 odrzucone na historii).
- **Dziennik** (gałąź `dane`, stan z 15:10 UTC): 301 sygnałów, 141 rozliczonych. Dotyczy trzech strategii technicznych; nowych hipotez nie ocenia.
- **Dane do testu:** zamknięcia miesiąca z cache świec dziennych, 54 instrumenty (indeksy bez VIX, akcje, metale szlachetne, krypto), `cfd monthly-test`
  (`src/cfd/validation/monthly.py`, test braku zaglądania w przyszłość w `tests/test_monthly.py`).
- **Wynik:** H3 przeszła historię i czeka na dziennik; H4 odrzucona. Silnik i ekran bez zmian.
- **Jak H3 będzie oceniana w przód** (ustalone teraz, przed zebraniem danych): reguła jest zamrożona, więc wynik od grudnia 2026 liczy
  `cfd monthly-test --since 2026-12` na samych cenach. Ogólne kryterium „50 rozliczonych sygnałów” tu nie pasuje, bo obserwacją jest miesiąc portfela,
  a nie sygnał. Kryterium H3: po **12 pełnych miesiącach** Sharpe portfela trendowego nie niższy niż „kup i trzymaj” **oraz** mniejsze największe obsunięcie,
  na całym zakresie i bez akcji. To słaby dowód (12 obserwacji): potwierdzenie statystyczne wymagałoby lat. Wcześniejsze odczyty są tylko informacją.
- **Zastrzeżenia do H3:** (1) pierwsze 15 lat próby odkrywczej to 1–2 instrumenty; (2) stopy bez dywidend i bez odsetek od gotówki;
  (3) lista akcji dobrana po fakcie i krypto zawyżają poziom stóp zwrotu w całym zakresie, dlatego wiążąca jest kontrola bez akcji;
  (4) nie uwzględniono przewalutowania przy zakupie zagranicznych akcji i ETF-ów; (5) w ostatnich 10 miesiącach trend wypadł gorzej niż „kup i trzymaj”
  (+0,25% wobec +0,71% miesięcznie), co mieści się w normalnej zmienności, ale pokazuje, że filtr kosztuje w rynku wzrostowym.
- **Stan reguły na koniec października 2026 (informacyjnie, nie rekomendacja):** w trendzie 15 z 17 indeksów, 0 z 4 metali, 2 z 3 krypto, 12 z 28 akcji.
- **Obserwacja z sesji 1** („wybicia bez strony SHORT”) nadal czeka na zapisanie jako hipoteza: w tej sesji limit dwóch hipotez został wykorzystany.
- **Wyjątek od reguły 5 (decyzja użytkownika, 2026-11-16):** stan reguły H3 jest pokazywany na ekranie już teraz, jako sekcja „Trend miesięczny”
  z oznaczeniem „hipoteza w trakcie potwierdzania, nie rekomendacja”. Status H3 się nie zmienia (czeka na ocenę w przód), a sygnały
  trzech strategii technicznych nie są przez nią wyróżniane ani filtrowane.

### Sesja 3 (2026-11-17, zadanie N4 z planu nocnego)

- **Hipoteza:** H5 (model przewidywań), zapisana i wypchnięta przed obliczeniami (commit „Hipoteza H5 … zapisana przed testem”).
- **Wynik:** odrzucona na historii dla obu horyzontów (tabela wyżej). Raport: `walidacja/model.md`, liczby: `walidacja/model.json`.
- **Zmiana po teście (zaostrzająca, nie luzująca):** baza per instrument przy < 250 wierszach treningowych zastąpiona częstością ogólną,
  bo instrument z kilkoma wierszami dostawał bazę 0 albo 1 i log loss bazy eksplodował (okno walk-forward 2018–2020 dla h = 20, log loss bazy 1,40).
  Wynik na teście bez zmian; średni BSS walk-forward po zmianie: h = 5 +0,0009, h = 20 −0,0083. Werdykt bez zmian.
- **Silnik:** model jest trenowany co tydzień (`recalc.yml`), prognozy liczone codziennie (`daily.yml`) z jakością z ostatniego testu.
  Dopóki jakość = „brak”, prognozy nie niosą informacji ponad częstość wzrostów i nie mogą wpływać na sygnały.

### Sesja 4 (2026-11-18)

- **Stare hipotezy:** H3 czeka na ocenę w przód od 2026-12 (brak pełnych miesięcy). Pozostałe zamknięte.
- **Dziennik** (gałąź `dane`, 06:02 UTC): 562 sygnały, 334 rozliczone. Wyniki informacyjnie (nie lekcje, hipotez w tej sprawie nie było):

  | Strategia, interwał | Rozliczonych | Średnio R | t |
  |---|---|---|---|
  | donchian_breakout 1h | 142 | +0,07 | 0,54 |
  | mean_reversion 1h | 103 | −0,57 | −5,33 |
  | trend_pullback 1h | 41 | +0,08 | 0,39 |
  | mean_reversion 4h | 15 | −0,89 | −6,06 |
  | donchian_breakout 4h | 15 | +0,07 | 0,16 |

  `mean_reversion` na żywo traci wyraźnie, zgodnie z walidacją na historii (−0,16 R po kosztach na 4h i 1h). Na 1d rozliczonych sygnałów prawie nie ma.
- **Nowe hipotezy:** H6 (wybicia 1d bez strony SHORT) zapisana od razu jako „czeka na dziennik”, bo pochodzi z obserwacji na już widzianych danych;
  dziś 1 rozliczony sygnał tego typu, kryterium wymaga 50 (szacunkowo kilka miesięcy). H7 (dryf po wynikach) wstrzymana z braku danych.
- **Do decyzji użytkownika:** czy pozwolić na pobieranie historii wyników z finance.yahoo.com (dopisanie hosta do środowiska i sprawdzenie regulaminu),
  czy szukać innego źródła; bez tego H7 nie da się uczciwie przetestować. Silnik i ekran bez zmian.
- **Dopisek do sesji 4:** H7 nie dała się przetestować, więc w jej miejsce zapisano H8 (ten sam efekt, inna miara niespodzianki, dane z SEC EDGAR).
  Limit dwóch hipotez na sesję liczony jest dla testów: w tej sesji przetestowana będzie jedna (H8); H6 czeka na dziennik bez testu.
- **Wynik H8:** odrzucona. Na dużych spółkach z USA w latach 2013–2026 po reakcji na wyniki nie ma dryfu w żadną stronę (różnica bliska zeru, znak niestabilny).
  Zgodne z literaturą: efekt osłabł po jego opisaniu i najsłabszy jest w największych, najpłynniejszych spółkach. Kod: `src/cfd/validation/earnings.py`,
  testy `tests/test_earnings.py`. Silnik i ekran bez zmian.

