### Punkt odniesienia (wszystkie sygnaly, bez filtra)

| Interwał | Strategia | Odkrywcza: n | Odkrywcza: śr. R | Potwierdzająca: n | Potwierdzająca: śr. R | Granica prób |
|---|---|---|---|---|---|---|
| 1d | donchian_breakout | 3970 | -0.032 | 2441 | -0.065 | 2017-03-15 |
| 1d | mean_reversion | 1734 | -0.152 | 1509 | -0.113 | 2017-03-15 |
| 1d | trend_pullback | 2761 | -0.025 | 1693 | -0.064 | 2017-03-15 |
| 1h | donchian_breakout | 5461 | -0.104 | 3173 | -0.191 | 2025-12-16 |
| 1h | mean_reversion | 2336 | -0.193 | 1841 | -0.104 | 2025-12-16 |
| 1h | trend_pullback | 3095 | -0.175 | 2247 | -0.116 | 2025-12-16 |
| 4h | donchian_breakout | 1298 | +0.001 | 704 | -0.170 | 2026-03-10 |
| 4h | mean_reversion | 551 | -0.233 | 455 | -0.107 | 2026-03-10 |
| 4h | trend_pullback | 719 | +0.024 | 554 | -0.242 | 2026-03-10 |

Filtrów z wystarczającą próbą: 318. Kandydatów na próbie odkrywczej: 5 (z samego przypadku spodziewane ok. 8). Potwierdzonych na próbie niewidzianej: 1 (z samego przypadku spodziewane ok. 0.2).

### Kandydaci i ich wynik na próbie potwierdzającej

| Int. | Strategia | Zakres | Cecha = wartość | Odkr.: n | Odkr.: śr. R | Odkr.: t | Potw.: n | Potw.: śr. R | Potw.: t | Wynik |
|---|---|---|---|---|---|---|---|---|---|---|
| 1d | donchian_breakout | stocks | vol = niska | 529 | +0.205 | 2.4 | 499 | +0.186 | 2.0 | POTWIERDZONY |
| 4h | donchian_breakout | crypto | d1_trend = zgodny | 488 | +0.154 | 2.1 | 49 | +0.284 | 1.2 | za mała próba |
| 4h | donchian_breakout | wszystkie | vol = niska | 365 | +0.186 | 2.2 | 212 | -0.155 | -1.5 | nie utrzymał się |
| 4h | donchian_breakout | crypto | vol = niska | 262 | +0.277 | 2.7 | 26 | -0.560 | -2.1 | za mała próba |
| 4h | trend_pullback | wszystkie | session = usa | 257 | +0.184 | 2.2 | 243 | -0.286 | -3.7 | nie utrzymał się |
