## E1. FRED

**Stan: zrobione bez klucza.** `FRED_API_KEY` nie jest ustawiony, więc ścieżka przez `api.stlouisfed.org` pozostaje niesprawdzona na żywo (bez klucza API odpowiada HTTP 400).

Co zrobione:
- `FredClient` dostał ścieżkę zapasową bez klucza: publiczny plik `https://fred.stlouisfed.org/graph/fredgraph.csv?id=SERIA&cosd=2010-01-01` (ten sam, który pobiera przycisk „Download” na stronie serii). Z kluczem nadal używane jest API.
- Pułapka: `fred.stlouisfed.org` zrywa połączenie (HTTP/2 INTERNAL_ERROR albo pusta odpowiedź), gdy User-Agent udaje przeglądarkę (`Mozilla/5.0 (compatible; ...)`). Z uczciwym `cfd-analyzer/0.2 (python-httpx)` odpowiada 200 za każdym razem (ok. 30 pobrań w tej sesji). Adapter wysyła ten nagłówek, odstęp 3 s na host, 2 ponowienia.
- `cfd bias check` (na żywo, 2026-11-10) dla wszystkich identyfikatorów z `config/fundamentals.yaml`:

| Seria | Wynik | Ostatnia obserwacja |
|---|---|---|
| DFII10 | OK | 2026-11-06 = 2,63 |
| DTWEXBGS | OK | 2026-11-06 = 121,88 |
| DGS10 | OK | 2026-11-06 = 4,86 |
| DGS2 | OK | 2026-11-06 = 4,51 |
| NFCI | OK (tygodniowa) | 2026-10-30 = −0,459 |
| BAMLH0A0HYM2 | OK, ale FRED udostępnia tylko ostatnie 3 lata (od 2023-11-10, 784 obs.) | 2026-11-06 = 3,42 |
| WCESTUS1 | **BŁĄD: HTTP 404, tej serii nie ma w FRED** (to identyfikator EIA) | – |

- Poprawka: `WCESTUS1` zastąpione serią z EIA `EIA:PET.WCESTUS1.W` (patrz E2). Pozostałe identyfikatory bez zmian.
- `cfd bias update`: bias policzony dla 30 instrumentów (ok. 80 s; 29 zapytań, z tego 20 do CFTC). `cfd bias show` pokazuje teraz także składowe.

Ocena sensowności (stan na 2026-11-10, okno 63 dni):
- Szeroki indeks dolara 118,07 → 121,88 (+3,2%, przy szczycie rocznego zakresu 117,4–122,0): składowa −1,55 dla złota, srebra, platyny, miedzi, ropy i krypto. Kierunek i skala zgodne z danymi.
- Realna rentowność 10Y 2,43 → 2,63: −0,68 dla złota i srebra.
- Indeksy USA −0,88: spread high yield 2,68 → 3,34 (−1,74), NFCI −0,545 → −0,459 (−0,66), 10Y 4,78 → 4,86 (−0,23). Wszystkie trzy składowe pokazują to samo zacieśnienie, więc wynik jest spójny.
- USDIDX +0,22: 2Y 4,37 → 4,51 (+0,44), pozycjonowanie neutralne.
- Wniosek: liczby są zgodne z ruchem serii, żadna składowa nie wygląda na błąd znaku ani jednostki. Zastrzeżenia: (1) to heurystyki, nie model, bez sprawdzenia skuteczności na historii; (2) dolar wchodzi do sześciu grup instrumentów, więc biasy są mocno skorelowane; (3) dla BAMLH0A0HYM2 odchylenie liczone jest tylko z 3 lat.

Zmienione: `src/cfd/fundamentals/fred.py`, nowy `src/cfd/fundamentals/_http.py`, `config/fundamentals.yaml`, `src/cfd/cli.py` (polecenia `bias`, `_context`: bias nie wymaga już klucza FRED), testy w `tests/test_fundamentals.py`, próbka `tests/fixtures/fred_fredgraph_BAMLH0A0HYM2.csv`.

Nie działa / niesprawdzone: ścieżka FRED z kluczem (parser pokryty testem, ale tylko na odpowiedzi w formacie z dokumentacji, nie na prawdziwej).

## E2. Zapasy (EIA) i pozycjonowanie (COT)

### EIA
- Nowy `src/cfd/fundamentals/eia.py` (`EiaClient`). Identyfikatory jak w API: `PET.WCESTUS1.W` (ropa bez SPR, tys. baryłek), `PET.WGTSTUS1.W` (benzyna ogółem), `NG.NW2_EPG0_SWO_R48_BCF.W` (gaz w magazynach, Lower 48, Bcf).
- Z `EIA_API_KEY`: API v2 `https://api.eia.gov/v2/seriesid/<ID>`. **Niesprawdzone na żywo**: klucza nie ma, API zwraca `API_KEY_MISSING` (HTTP 403). Format danych (`response.data[].period/value`) wpisany z dokumentacji; próbka z prawdziwej odpowiedzi to tylko komunikat błędu.
- Bez klucza albo gdy API zawiedzie: publiczna strona historii na `www.eia.gov/dnav/...` (dla PET `LeafHandler.ashx?n=PET&s=...&f=W`, dla NG `dnav/ng/hist/<seria>w.htm`). `robots.txt` EIA nie blokuje `/dnav/`, dane rządowe USA są w domenie publicznej, jedno zapytanie na serię na przebieg, odstęp 5 s. Sprawdzone na żywo: ropa 2301 obs. do 2026-10-30 = 409 760, benzyna 1922 obs. = 208 958, gaz 879 obs. = 3 801.
- Składowe: zapasy są sezonowe (zwłaszcza gaz i benzyna), więc doszła opcja `transform: yoy`: liczona jest 28-dniowa zmiana nadwyżki wobec tego samego tygodnia rok wcześniej, znak −1. Test pokazuje, że bez tej transformacji sama sezonowość daje fałszywy sygnał.
- Wyniki 2026-11-10: ropa +1,22 (zapasy −14,4 mln b w 4 tygodnie, rok wcześniej +0,9 mln), benzyna −2,00 (+4,2 mln b, rok wcześniej −13,1 mln), gaz −0,19 (+301 Bcf, rok wcześniej +274 Bcf).

### COT
- Nowy `src/cfd/fundamentals/cot.py` (`CotClient`), API Socrata CFTC bez klucza, raporty „futures only”: `legacy` = zbiór `6dca-aqww` (non-commercial), `disaggregated` = `72hh-3qpy` (managed money), `tff` = `gpe5-46if` (leveraged funds). Wszystkie trzy zbiory sprawdzone na żywo, ostatni raport 2026-11-03. Pobierane 5 lat (261 raportów na kontrakt), odstęp 1 s.
- Nowy typ składowej `type: positioning` (`positioning_score` w `bias.py`, korzysta z `positioning_percentile`): percentyl pozycji netto na tle 156 raportów; ≥ 90 daje −1…−2, ≤ 10 daje +1…+2, w środku 0. Progi, okno i znak konfigurowalne per składowa.
- Mapowanie instrument → kod kontraktu w `config/fundamentals.yaml`, sekcja `cot_contracts` (20 instrumentów: metale, energia, rolne, USDIDX). Kody wzięte z raportu z 2026-11-03 i każdy sprawdzony zapytaniem.
- Odczyty 2026-11-10 (percentyl → składowa): LEANHOGS 1 → +1,94; NATGAS 1 → +1,94; COFFEE 2 → +1,81; PALLADIUM 3 → +1,68; SILVER 4 → +1,55; COCOA 9 → +1,10; GASOLINE 92 → −1,23; SUGAR 96 → −1,55; pozostałe 12 w strefie neutralnej (m.in. GOLD 22, COPPER 47, OIL.WTI ok. 10 (tuż nad progiem), OIL 30).

### Bias dla instrumentów z zadania
| Instrument | Bias | Składowe |
|---|---|---|
| OIL | −0,11 | zapasy ropy +1,22; dolar −1,55; COT 0 (percentyl 30) |
| OIL.WTI | −0,11 | zapasy ropy +1,22; dolar −1,55; COT 0 (percentyl 10) |
| GASOLINE | −0,67 | zapasy benzyny −2,00; zapasy ropy +1,22; COT −1,23 (percentyl 92) |
| NATGAS | +0,87 | magazyny gazu −0,19; COT +1,94 (percentyl 1) |

### Inne zmiany
- `SeriesRouter` (`fundamentals/sources.py`): prefiks identyfikatora wybiera źródło (`EIA:`, `CFTC:`, bez prefiksu FRED).
- Kontrola świeżości: składowa jest odrzucana z błędem, gdy ostatnia obserwacja jest starsza niż `max_age_days` (45). Wcześniej wycofana seria dawałaby po cichu wynik 0.
- Testy: `tests/test_fundamentals.py` (21 testów) na próbkach `fred_fredgraph_BAMLH0A0HYM2.csv`, `eia_hist_WCESTUS1.html`, `eia_hist_nw2_epg0_swo_r48_bcfw.html` (obie strony EIA skrócone do lat 2023–2026), `eia_api_key_missing.json`, `cftc_disaggregated_088691.json`, `cftc_error.json`. Całość: `pytest -q` → 117 passed.

### Ograniczenia
- Składowa COT w strefie neutralnej ma wartość 0 i wchodzi do średniej, więc rozcieńcza pozostałe składowe (np. GOLD: −0,68 i −1,55 dają −0,74 zamiast −1,12). To świadomy, ostrożny wybór; alternatywa (pomijanie neutralnej) wymaga decyzji.
- Dla OIL (Brent) użyty jest kontrakt „BRENT LAST DAY” z NYMEX (otwarte pozycje ok. 208 tys.). Główny Brent na ICE Europe nie jest w raportach CFTC.
- Instrumenty rolne, PALLADIUM mają bias wyłącznie z COT: zwykle 0, przy skrajnościach od razu ±1…2.
- Indeksy akcji i krypto nie dostały składowej COT (nie ustalałem, która grupa uczestników ma tam sens kontrariański).
- Skuteczność składowych kontrariańskich nie była testowana na historii cen.
- Poza moimi plikami zostały nieaktualne opisy: `README.md` (wiersz „zapasy EIA i COT: niezaimplementowane”), `.env.example` (brak `EIA_API_KEY`), `dashboard.py` (tekst „Wymaga FRED_API_KEY”).

## E3. Akcje

Pominięte: brak listy spółek (decyzja użytkownika). Nic nie zmieniono.
