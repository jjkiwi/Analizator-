# Rejestr hipotez („lekcje” silnika)

Silnik nie uczy się sam. Zmiany w strategiach wprowadza Claude Code w sesjach uruchamianych **ręcznie przez użytkownika**
(decyzja z 2026-11-15: kontrola zużycia tokenów). Ten plik jest pamięcią między sesjami: każda sesja zaczyna od zera.

## Jak poprosić o sesję

Wystarczy napisać: „sesja nauki”. Claude Code wykonuje wtedy procedurę poniżej i kończy raportem.

## Procedura sesji

1. `git pull`, przeczytaj ten plik i `walidacja/` (ostatnie przeliczenie). Dziennik: `git fetch origin dane` i `git show origin/dane:sygnaly.csv`
   (skan co godzinę nadpisuje tę gałąź eksportem dziennika; artefaktów Actions nie da się pobrać ze środowiska Claude Code).
2. **Najpierw rozlicz stare hipotezy**: dla każdej w stanie „czeka na dziennik” sprawdź sygnały zebrane PO dacie jej zapisania.
   Hipotezy dziennika (H6, H17, H18): `git show origin/dane:sygnaly.csv > s.csv && python -m cfd.validation.journal_ctx s.csv`
   (błąd po skupiskach; nowe hipotezy w przód dopisuj do `FORWARD` w `src/cfd/validation/journal_ctx.py`). H3: `cfd monthly-test --since 2026-12`.
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
| H9 | 2026-11-18 | **Zarządzanie zmiennością.** Koszyk indeksów (kategoria `indices` bez VIX i USDIDX, równe wagi, dzienne stopy) trzymany z ekspozycją zmienianą raz w miesiącu: w = min(1, σ_cel / σ_ost), gdzie σ_ost to zmienność koszyka z ostatnich 21 sesji, a σ_cel to średnia σ_ost z całej wcześniejszej historii (przyczynowo). Uzasadnienie: zmienność jest przewidywalna, a wysokiej zmienności nie towarzyszy proporcjonalnie wyższa stopa zwrotu (Moreira i Muir 2017), więc mniejsza ekspozycja w burzliwych okresach poprawia relację zysku do ryzyka. Bez dźwigni (w ≤ 1). | Porównanie z koszykiem o stałej ekspozycji 1, oba z kosztem spreadu od zmiany ekspozycji, bez swapu (jak ETF). Podział w czasie 60/40. Odkrywcza i potwierdzająca: Sharpe zarządzanego wyższy o ≥ 0,10 **oraz** mniejsze największe obsunięcie. Dodatkowo bootstrap blokowy (bloki 21 sesji) różnicy Sharpe’a na całej próbie: p < 0,10. | 16 indeksów, 1966–2026, średnia ekspozycja 0,90. Odkrywcza (do 2002-12): Sharpe 0,78 wobec 0,78 (**różnica 0,00, niespełnione**), obsunięcie −48,5% wobec −52,6%. Potwierdzająca: Sharpe 0,67 wobec 0,60 (+0,07, niespełnione), obsunięcie −37,9% wobec −52,2%. Bootstrap p = 0,22. | odrzucona na historii | – |
| H10 | 2026-11-18 | **Przełom miesiąca.** Stopy indeksów koncentrują się w ostatniej sesji miesiąca i pierwszych trzech sesjach następnego (przepływy płacowe i funduszy; efekt opisany od lat 80.). Ten sam koszyk co H9; dla każdego indeksu i miesiąca: suma stóp z 4 sesji przełomu minus 4 × średnia dzienna stopa pozostałych sesji tego miesiąca; średnia po indeksach daje jedną obserwację na miesiąc. | Podział miesięcy w czasie 60/40. Odkrywcza: średnia > 0, t ≥ 2. Potwierdzająca: średnia > 0, t ≥ 1,65 **oraz** średnia suma stóp koszyka z 4 sesji przełomu > 0,15% (koszt praktyczny dla CFD: spread na wejściu i wyjściu oraz 4 noce swapu długiej pozycji). | Odkrywcza (444 miesiące, 1965–2002): nadwyżka +0,38 pp, t = 3,78 (spełnione). Potwierdzająca (297 miesięcy od 2002-02): +0,09 pp, **t = 0,64 (niespełnione)**; suma 4 sesji +0,18%. | odrzucona na historii | – |
| H11 | 2026-11-18 | **Kupno po skoku strachu (VIX).** Gdy VIX zamyka się powyżej 90. percentyla swoich zamknięć z poprzednich 252 sesji (przyczynowo), S&P 500 w kolejnych 20 sesjach rośnie bardziej niż przeciętnie. Uzasadnienie: premia za ryzyko jest najwyższa, gdy inwestorzy płacą najwięcej za ochronę; to odwrotność odruchu „uciekać przy panice”. Dane: `^VIX` i `^GSPC` z Yahoo. Wejście na zamknięciu sesji po sygnale, wyjście 20 sesji później; po sygnale kolejne liczą się dopiero po wyjściu (epizody bez nakładania). | Podział epizodów w czasie 60/40. Odkrywcza: średnia stopa epizodu minus średnia 20-sesyjna stopa ze wszystkich dni > 0, t ≥ 2. Potwierdzająca: różnica > 0, t ≥ 1,65 **oraz** średnia stopa epizodu > 0,5% (spread i 20 nocy swapu długiej pozycji CFD na US500). | 120 epizodów 1991–2026. Odkrywcza (72): średnio +0,85% wobec +0,60% wszystkich dni, nadwyżka +0,26 pp, t = 0,38. Potwierdzająca (48): +1,30% wobec +1,07%, nadwyżka +0,22 pp, t = 0,29. Kierunek zgodny, siła znikoma: po panice rynek rośnie mniej więcej tak jak zawsze. | **odrzucona** | Sesja 6 |
| H12 | 2026-11-18 | **Reguła 200 sesji dla pojedynczych spółek.** Spółkę trzyma się tylko, gdy jej zamknięcie jest powyżej średniej z 200 sesji (sprawdzane codziennie, zmiana na następnym zamknięciu), inaczej gotówka. Uzasadnienie: trend na horyzoncie miesięcy (H3 przeszła historię na koszykach) powinien chronić także pojedyncze akcje przed długimi spadkami; to pytanie praktyczne dla posiadanych spółek. Zakres neutralny wobec portfela: 30 obecnych spółek Dow Jones (dane Yahoo). | Portfel równych wag reguły wobec portfela równych wag „kup i trzymaj” z tych samych spółek, koszt 0,1% od każdej zmiany, bez dywidend. Podział w czasie 60/40. Odkrywcza i potwierdzająca: Sharpe reguły wyższy o ≥ 0,10 **oraz** mniejsze największe obsunięcie. Bootstrap blokowy różnicy Sharpe’a na całej próbie: p < 0,10. Zastrzeżenie: obecny skład Dow Jones to spółki, które przetrwały (sprzyja „kup i trzymaj”). | 1962–2026, 30 spółek. Odkrywcza: Sharpe 1,08 wobec 1,08, obsunięcie −24% wobec −50%, roczna stopa 11,3% wobec 18,2%. Potwierdzająca (2001–2026): Sharpe 0,71 wobec 0,78, obsunięcie −26% wobec −46%, 6,3% wobec 13,7%. Bootstrap p = 0,57. Reguła połowi obsunięcie, ale kosztem połowy zysku; Sharpe nie rośnie. | **odrzucona** | Sesja 6 |
| H13 | 2026-11-18 | **Wzrost w dniu decyzji Fed (FOMC).** S&P 500 w dniu ogłoszenia decyzji z planowego posiedzenia FOMC (stopa od zamknięcia dnia poprzedniego do zamknięcia dnia decyzji) rośnie bardziej niż w przeciętny dzień. Uzasadnienie: opisany w literaturze „dryf przed FOMC” (Lucca i Moench 2015) jako premia za ryzyko związane z decyzją; daty posiedzeń są znane z wyprzedzeniem, więc reguła jest przyczynowa i prosta dla CFD (jedna noc). Zagrożenie znane z góry: w literaturze efekt słabnie po 2015 r. Dane: daty planowych posiedzeń ze strony federalreserve.gov (1994–2026), `^GSPC` z Yahoo. | Podział zdarzeń w czasie 60/40. Odkrywcza: średnia stopa w dniu decyzji minus średnia stopa wszystkich dni w tym samym okresie > 0, t ≥ 2. Potwierdzająca: nadwyżka > 0, t ≥ 1,65 **oraz** średnia stopa w dniu decyzji > 0,10% (spread i jedna noc swapu US500). | 258 decyzji 1994–2026. Odkrywcza (1994–2013, 154): +0,35% w dniu decyzji wobec +0,03% przeciętnie, nadwyżka +0,31 pp, t = 3,23, 60% dni wzrostowych. Potwierdzająca (2013–2026, 104): +0,09% wobec +0,05%, nadwyżka +0,04 pp, t = 0,33, 47% wzrostowych. Efekt był silny i zniknął po jego opisaniu, tak jak przewidywała literatura. | **odrzucona** | Sesja 7 |
| H14 | 2026-11-18 | **Dzień przed świętem giełdowym w USA.** S&P 500 w ostatniej sesji przed dniem roboczym bez notowań (święto) rośnie bardziej niż w przeciętny dzień. Uzasadnienie: znany od dekad „efekt przedświąteczny” (Ariel 1990), tłumaczony zamykaniem krótkich pozycji przed przerwą; terminy świąt są znane z góry. Święta rozpoznaję z danych (dzień roboczy bez sesji), z wyłączeniem zamknięć nieplanowanych nieznanych dzień wcześniej (11–14.09.2001, 29–30.10.2012). Okres 1970–2026. | Jak H13: podział zdarzeń 60/40; odkrywcza nadwyżka > 0, t ≥ 2; potwierdzająca nadwyżka > 0, t ≥ 1,65 **oraz** średnia stopa w tym dniu > 0,10%. | 489 dni przedświątecznych 1970–2026. Odkrywcza (do 2005, 293): +0,16% wobec +0,03%, nadwyżka +0,13 pp, t = 2,77, 60% wzrostowych. Potwierdzająca (2005–2026, 196): +0,13% wobec +0,04%, nadwyżka +0,09 pp, **t = 1,45 (próg 1,65)**, 63% wzrostowych. Kierunek trwały, siła za mała przy ~9 zdarzeniach rocznie. | **odrzucona** | Sesja 7 |
| H15 | 2026-11-18 | **Sygnał zgodny z kierunkiem newsów jest lepszy.** Sygnały, dla których istotne newsy o instrumencie z 12 h przed sygnałem wskazują ten sam kierunek (kontekst `news` = `zgodny`), mają wyższy wynik w R niż sygnały z newsami w przeciwną stronę (`przeciwny`). Uzasadnienie: reakcja rynku na informację rozkłada się w czasie (dryf po newsie), więc pozycja z newsem płynie z prądem. Kierunek newsa pochodzi z klasyfikatora reguł (słowa kluczowe), nie z LLM. Zapisana 2026-11-18 22:51 UTC. | Etap 1, dziennik do chwili zapisania (`created_at` < 2026-11-18 22:51): wynik R pomniejszony o średnią swojej pary strategia × interwał (żeby nie mylić efektu newsa z różnicą strategii); różnica średnich zgodny − przeciwny > 0, t ≥ 2 przy błędzie liczonym po skupiskach (sygnały z tej samej godziny świecy to jedno skupisko). Etap 2, dziennik po zapisaniu: ≥ 50 rozliczonych w każdej grupie, różnica > 0, t ≥ 1,65 **oraz** średni surowy wynik grupy zgodnej > 0 R. | Etap 1 (461 rozliczonych, 7 dni): zgodne 93, przeciwne 85. Surowo +0,24 R wobec −0,33 R, ale większość tej różnicy to skład strategii (przeciwne częściej trafiają na `mean_reversion`). Po odjęciu średniej strategii: +0,18 R, **t = 0,98** (86 skupisk). Kierunek zgodny z hipotezą, dowód za słaby. | **odrzucona na historii** | – |
| H16 | 2026-11-18 | **Sygnał tuż przed ważną publikacją makro jest gorszy.** Sygnały wykryte na mniej niż 2 h przed publikacją makro najwyższej wagi (`macro_next_h` < 2) mają niższy wynik w R niż pozostałe. Uzasadnienie: skok zmienności w chwili publikacji przypadkowo zrywa stop albo zysk, niezależnie od sygnału technicznego; praktyczny filtr „nie wchodź przed danymi”. Zapisana 2026-11-18 22:51 UTC. | Etap 1, dziennik do chwili zapisania: wynik R pomniejszony o średnią pary strategia × interwał; różnica średnich pozostałe − przed publikacją > 0, t ≥ 2 (skupiska jak w H15). Etap 2, dziennik po zapisaniu: ≥ 50 rozliczonych sygnałów przed publikacją, różnica > 0, t ≥ 1,65. | Etap 1: 75 sygnałów przed publikacją, 313 pozostałych. Surowo −0,20 R wobec −0,04 R; po odjęciu średniej strategii różnica +0,19 R na korzyść pozostałych, **t = 1,44** (112 skupisk). Kierunek zgodny, dowód za słaby. | **odrzucona na historii** | – |
| H17 | 2026-11-19 | **Wybicia na 1h zarabiają po kosztach na żywo.** `donchian_breakout` 1h, wszystkie instrumenty, obie strony. Uzasadnienie: w dzienniku 12–18.11 +0,22 R na 195 sygnałach (t po skupiskach 1,86); walk-forward na historii nie dał tu przewagi po kosztach, więc to sprzeczność do rozstrzygnięcia na nowych danych. Ponieważ pomysł wziął się z dziennika, liczą się **wyłącznie** sygnały zapisane po 2026-11-19 00:31 UTC (jak H6). | Tylko dziennik w przód (`created_at` ≥ 2026-11-19 00:31): ≥ 100 rozliczonych, średni wynik R po kosztach > 0, t ≥ 1,65 po skupiskach (interwał + godzina świecy). Historia już znana i sprzeczna (wpisana jako zastrzeżenie). | Historia: brak przewagi po kosztach (walk-forward 1h). Dziennik przed zapisaniem: +0,22 R, t 1,86 (źródło pomysłu, nie dowód). | czeka na dziennik | |
| H18 | 2026-11-19 | **`mean_reversion` na 1h i 4h traci po kosztach na żywo.** Hipoteza ostrzegawcza: jeśli się potwierdzi, użytkownik dostaje rekomendację, by ekran oznaczał te sygnały jako „historycznie stratne” (decyzja użytkownika; nic nie trafia do `alert_strategies`). Uzasadnienie: dziennik 12–18.11: 1h −0,55 R (t po skupiskach −4,34), 4h −0,91 R na 16; zgodne z historią (walk-forward bez przewagi po kosztach). Liczą się wyłącznie sygnały zapisane po 2026-11-19 00:31 UTC. | Tylko dziennik w przód: ≥ 100 rozliczonych (1h i 4h razem), średni wynik R < 0, t ≤ −1,65 po skupiskach. | Historia: brak przewagi po kosztach (zgodne). Dziennik przed zapisaniem: wyraźna strata (źródło pomysłu, nie dowód). | czeka na dziennik | |

Liczba hipotez przetestowanych do tej pory: **18** (nie licząc 276 filtrów z testu kontekstowego i 639 kombinacji strategii z walidacji).

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

### Sesja 5 (2026-11-18)

- **Stare hipotezy:** H3 czeka na pełne miesiące od grudnia. H6: 0 sygnałów `donchian_breakout` 1d SHORT od 2026-11-18 (wymagane 50 rozliczonych).
- **Dziennik** (13:02 UTC): 625 sygnałów, 386 rozliczonych.
- **H9 (zarządzanie zmiennością): odrzucona.** Zmniejszanie ekspozycji w okresach wysokiej zmienności wyraźnie ogranicza największe obsunięcie
  (−38% wobec −52% w nowszych danych), ale nie poprawia relacji zysku do ryzyka ponad próg (Sharpe +0,00 i +0,07). Efekt istnieje jako ochrona
  przed spadkami, nie jako przewaga.
- **H10 (przełom miesiąca): odrzucona.** Silny efekt do 2002 r. (t = 3,8) praktycznie zniknął później (t = 0,6), zgodnie z literaturą o zanikaniu
  anomalii kalendarzowych po ich opisaniu.
- Kod: `src/cfd/validation/calendar_vol.py`, testy `tests/test_calendar_vol.py`. Silnik i ekran bez zmian.
- **Wniosek z sesji 1–5:** jedyną hipotezą, która przeszła historię, jest trend miesięczny (H3), a jej wartością jest ograniczanie obsunięć,
  nie wyższy zysk. Tę samą właściwość pokazała H9. Kierunek na kolejne sesje: zarządzanie ryzykiem portfela (kiedy zmniejszać ekspozycję),
  a nie przewidywanie kierunku.

### Sesja 6 (2026-11-18)

- Dziennik (gałąź `dane`, 14:09 UTC): 640 sygnałów, 395 rozliczonych. H6: 0 sygnałów SHORT donchian 1d od 2026-11-18 (potrzeba 50). H3: ocena w przód od 2026-12.
- H11 (kupno po skoku VIX): **odrzucona**. Nadwyżka po panice +0,2 pp na 20 sesji, t < 0,4 w obu połowach. Popularna rada „kupuj, gdy jest strach” nie daje przewagi ponad zwykłe trzymanie indeksu.
- H12 (reguła 200 sesji na spółkach Dow 30): **odrzucona** według kryterium (Sharpe nie rośnie, p = 0,57). Obsunięcie spada z ~−50% do ~−25%, ale roczna stopa spada o połowę. Wniosek praktyczny taki sam jak przy H3: reguła trendu to narzędzie ograniczania ryzyka, nie źródło zysku.
- Kod: `src/cfd/validation/risk.py`, testy przyczynowości `tests/test_risk.py`.

### Sesja 7 (2026-11-18)

- Dziennik (15:22 UTC): 646 sygnałów, 402 rozliczone. H6: nadal 0 sygnałów SHORT donchian 1d. H3: ocena od 2026-12.
- Obserwacja z dziennika (bez hipotezy, nie zmienia silnika): `mean_reversion` przegrywa coraz wyraźniej, 1h −0,65 R (123, t −6,9), 4h −0,91 R (16).
- H13 (dzień decyzji FOMC): **odrzucona**. W latach 1994–2013 nadwyżka +0,31 pp (t 3,2), po 2013 +0,04 pp (t 0,3). Lekcja: efekt opisany w literaturze (2015) przestał działać; znane anomalie kalendarzowe nie są dobrym tropem.
- H14 (dzień przed świętem w USA): **odrzucona**, najbliżej progu ze wszystkich dotąd: potwierdzająca t = 1,45, średnio +0,13% przy 63% dni wzrostowych. Za mało zdarzeń (~9 rocznie), żeby to odróżnić od szumu; progu nie obniżam.
- Daty FOMC (planowe posiedzenia 1994–2026) zapisane w `walidacja/fomc_daty.csv`, pobrane jednorazowo z federalreserve.gov (odstęp 3 s, brak robots.txt). Kod: `src/cfd/validation/events.py`, testy `tests/test_events.py` na zapisanych próbkach stron.

### Sesja 8 (2026-11-18)

- Dziennik (22:50 UTC): 736 sygnałów, 461 rozliczonych z 7 dni handlu. H6: nadal 0. H3: od 2026-12.
- Pierwsze hipotezy oparte wyłącznie na dzienniku (newsy i makro nie mają archiwum, więc nie da się ich sprawdzić na historii).
- H15 (zgodność z newsami): **odrzucona na etapie 1**, t = 0,98. Lekcja: surowe porównanie (+0,24 R wobec −0,33 R) wyglądało obiecująco, ale wynikało głównie z tego, która strategia dała sygnał. Porównania kontekstu zawsze w obrębie strategii.
- H16 (przed publikacją makro): **odrzucona na etapie 1**, t = 1,44.
- Lekcja metodyczna: sygnały z tej samej świecy na wielu instrumentach nie są niezależne. Liczone po skupiskach t spada, np. `mean_reversion` 1h z −5,75 do −4,34 (nadal wyraźna strata). Od tej sesji oceny dziennika liczę po skupiskach (`src/cfd/validation/journal_ctx.py`).
- Obserwacja (bez hipotezy, limit dwóch na sesję): `donchian_breakout` 1h w dzienniku +0,22 R na 195 sygnałach, t po skupiskach 1,86. Historia (walk-forward) nie dała tu przewagi po kosztach, a dziennik to 7 dni jednego okresu rynku. Kandydat na hipotezę z oceną wyłącznie w przód w następnej sesji.
- H15 i H16 można postawić ponownie za kilka tygodni na większym dzienniku, jako nowe próby (licznik rośnie).

### Sesja 9 (2026-11-19)

- Dziennik (00:30 UTC): 739 sygnałów, 463 rozliczone (tylko +2 od sesji 8). H6: 0 sygnałów. H3: od 2026-12. ANT.US: jeszcze bez notowań (debiut dziś).
- H17 (wybicia 1h zarabiają) i H18 (`mean_reversion` 1h/4h traci): zapisane 00:31 UTC jako **hipotezy wyłącznie w przód**, bo oba pomysły pochodzą z dziennika, który już widziałem. Wcześniejsze 463 sygnały nie liczą się jako dowód.
- Nowe narzędzie: `python -m cfd.validation.journal_ctx sygnaly.csv` rozlicza H6, H17, H18 jednym poleceniem (t po skupiskach), żeby kolejne sesje były tańsze.
- Rada na kolejne sesje: przy tempie ~100 rozliczeń na dzień roboczy H17 i H18 mogą mieć werdykt po ok. 1–2 tygodniach. Sesje częstsze niż co kilka dni niewiele dodadzą, dopóki dziennik nie urośnie.


### Sesja 10 (2026-11-19)

- Dziennik (11:45 UTC): 784 sygnały, 507 rozliczonych. H6: 0/50. H17: 2/100 (−1,11 R, za wcześnie). H18: 0/100. ANT.US: notowania od otwarcia w USA, jeszcze brak.
- H3: sprawdzone, że ocena w przód działa (`cfd monthly-test --since 2026-12` zwraca n = 0 bez błędu; na oknie od 2026-01 liczy 10 miesięcy). Pierwszy miesiąc do oceny: grudzień 2026, ocena po 2027-01-01.
- **Świadomie bez nowych hipotez.** Po 18 próbach i 0 potwierdzeniach każda kolejna próba na „przeoranej” historii zwiększa szansę trafienia z przypadku, a dziennik przybywa wolniej niż sesje. Licznik bez zmian: 18.
