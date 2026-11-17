# Plan na noc 2026-11-17/18 (ok. 6 godzin)

Prośba użytkownika: rano ładny dashboard („centrum dowodzenia”), newsy napływające co kilka minut, co się dzieje na świecie i jak to
wpływa na giełdę, formacje techniczne na wykresach, model przewidywań trenowany cały czas, z testami stosowanymi przy uczeniu modeli.
Strona https://jjkiwi.github.io/Analizator-/ pokazuje 404 (Pages publikuje gałąź `dane`, na której do 23:05 nie było ekranu).

| Nr | Zadanie | Kto | Stan |
|---|---|---|---|
| N1 | Strona bez 404: ekran na gałęzi `dane` (poprawka wypchnięta 23:26, działa od skanu 00:02 UTC) — sprawdzić | koordynator | w toku |
| N2 | Tor „na żywo”: zadanie `lancuch` zamiast spać godzinę co ~4 min pobiera newsy i notowania, wypycha `live.json` na gałąź `live`; strona doczytuje go co 2 min (raw.githubusercontent.com, CORS) | koordynator | |
| N3 | Formacje techniczne: wsparcia/opory, linie trendu, podwójny szczyt/dno, trójkąty, wybicia z konsolidacji (`features/patterns.py`) + wykresy SVG z naniesionymi formacjami (`charts.py`) + testy | subagent A | |
| N4 | Model przewidywań: cechy, cel (kierunek za 5 i 20 sesji), regresja logistyczna, walidacja ze zbiorem treningowym/walidacyjnym/testowym, walk-forward z oczyszczaniem i embargiem, metryki (Brier, log loss, AUC, kalibracja), porównanie z poziomem bazowym, test permutacyjny; cotygodniowe ponowne trenowanie; dziennik prognoz oceniany w przód | subagent B | |
| N5 | Dashboard „centrum dowodzenia”: pasek notowań, pasek newsów, mapa rynku (zmiany dzienne), newsy z wpływem na instrumenty, wykresy z formacjami, prognozy modelu z jakością, trend miesięczny, spółki, kalendarz, sygnały; auto-odświeżanie; telefon i komputer | koordynator | |
| N6 | Integracja, testy, zrzuty ekranu, dokumentacja (WYNIKI, HIPOTEZY), weryfikacja w Actions | koordynator | |

Zasady bez zmian (`CLAUDE.md`): bez zleceń, bez poluzowania walidacji, uczciwe prawdopodobieństwa (model pokazuje jakość obok prognozy).
Po wyczerpaniu limitu praca wznawia się sama (rutyna co godzinę do rana).
