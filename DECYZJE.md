# Decyzje do podjęcia

Odpowiedz przy każdym punkcie (wystarczy jedno słowo lub linijka). Klucze i tokeny wpisuj **tylko do pliku `.env`**
na swoim komputerze, nie do czatu i nie do tego pliku.

## Blokujące (bez nich część systemu nie ruszy)

1. **Koszty transakcyjne XTB.** Backtest liczy na moich założeniach (`cost_defaults` w `config/instruments.yaml`).
   Potrzebne ze specyfikacji instrumentów w xStation: spread, punkty swapowe long/short, wartość lota.
   Możesz dać zrzuty ekranu albo przepisać dla kilkunastu najważniejszych instrumentów.
   Odpowiedź: ...

2. **Gdzie program ma działać całą dobę?** Reakcja na newsy wymaga ciągłej pracy.
   a) własny komputer (działa tylko, gdy jest włączony), b) darmowy/tani VPS, c) Raspberry Pi lub podobne.
   Odpowiedź: ...

3. **Telegram.** Załóż bota przez @BotFather i wpisz `TELEGRAM_BOT_TOKEN` oraz `TELEGRAM_CHAT_ID` do `.env`.
   Bez tego alerty wypisują się tylko w konsoli. Zrobione? ...

4. **Klucz FRED** (darmowa rejestracja na fred.stlouisfed.org) do `.env` jako `FRED_API_KEY`.
   Bez niego nie ma biasu fundamentalnego. Zrobione? ...

## Zakres

5. **Trzecia kryptowaluta.** Wpisałem Solanę. Zostaje, czy inna (np. XRP)? ...

6. **Lista akcji.** Podaj tickery z giełdą (np. `AAPL` USA, `PKN` GPW). ...

7. **Cynk i nikiel.** Brak darmowego źródła danych. a) pominąć, b) szukać dalej. ...

8. **Interwały skanera.** Domyślnie D1 i H4. Dodać H1 (więcej sygnałów, więcej szumu, historia tylko ~2 lata)? ...

## Newsy

9. **Klasyfikacja newsów.** a) same reguły (darmowe, słabo oceniają kierunek), b) reguły + API Anthropic
   (płatne za użycie, wstępnie grosze dziennie, dokładny koszt policzy Claude Code w zadaniu C3),
   c) reguły + darmowy model lokalny (wymaga mocniejszego komputera). ...

10. **Próg alertów newsowych.** a) tylko pilne (waga 3), b) pilne i istotne (waga ≥ 2, wyraźnie więcej powiadomień). ...

11. **Cisza nocna.** Wstrzymywać powiadomienia w określonych godzinach? Jeśli tak, w jakich? ...

12. **Języki źródeł.** Obecnie angielski i polski. Wystarczy? ...

## Później

13. **Ceny na żywo.** Założyć konto demo u brokera z API (Capital.com lub IG) jako darmowe źródło kwotowań CFD,
    czy zostać przy danych opóźnionych o kilkanaście minut? ...

14. **Które strategie mają wysyłać alerty.** Do rozstrzygnięcia po raporcie walidacji (zadanie B1).
    Do tego czasu wszystkie tylko zapisują sygnały w dzienniku. ...

15. **Panel.** Statyczny plik HTML (`cfd dashboard`) wystarczy na teraz, czy budować pełną aplikację PWA? ...

16. **Kalkulator pozycji.** Jakie ryzyko na transakcję przyjąć domyślnie (np. 1% kapitału) i w jakiej walucie jest rachunek? ...

## Nowe pytania (dopisuje Claude Code)

