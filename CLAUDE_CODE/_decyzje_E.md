## Nowe pytania (E. Fundamenty)

1. **Klucz FRED** (`FRED_API_KEY`): nadal go nie ma. Bias działa bez niego przez publiczny plik `fredgraph.csv`, więc klucz nie jest już warunkiem. Warto go jednak dodać: API jest oficjalną, stabilniejszą drogą, a ścieżka z kluczem nie została dotąd sprawdzona na żywo.
2. **Klucz EIA** (`EIA_API_KEY`, darmowa rejestracja: eia.gov/opendata/register.php): brak. Zapasy pobierane są ze stron historii na www.eia.gov (działa). Po dodaniu klucza trzeba raz uruchomić `cfd bias check` i potwierdzić, że ścieżka API v2 działa, bo powstała bez możliwości sprawdzenia. Do `.env.example` trzeba dopisać `EIA_API_KEY=`.
3. **Neutralne pozycjonowanie COT**: czy ma liczyć się jako 0 w średniej biasu (obecnie tak, rozcieńcza inne składowe), czy być pomijane, gdy percentyl jest między 10 a 90?
4. **Brent w COT**: dla OIL używam kontraktu „BRENT LAST DAY” z NYMEX. Alternatywy: pozycjonowanie z WTI albo brak składowej COT dla OIL. Która wersja?
5. **COT dla indeksów i krypto**: dodać (raport TFF, np. E-mini S&P 500 `13874A`, Nasdaq `209742`, Bitcoin CME `133741`)? Jeśli tak, to którą grupę traktować kontrariańsko: leveraged funds czy asset managers?
6. **E3**: nadal potrzebna lista spółek.
