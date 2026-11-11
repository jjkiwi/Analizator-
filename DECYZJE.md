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

