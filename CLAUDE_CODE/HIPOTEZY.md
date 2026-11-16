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

Liczba hipotez przetestowanych do tej pory: **2** (nie licząc 276 filtrów z testu kontekstowego i 639 kombinacji strategii z walidacji).

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

