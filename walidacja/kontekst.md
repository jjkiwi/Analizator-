### Punkt odniesienia (wszystkie sygnaly, bez filtra)

| Interwał | Strategia | Odkrywcza: n | Odkrywcza: śr. R | Potwierdzająca: n | Potwierdzająca: śr. R | Granica prób |
|---|---|---|---|---|---|---|
| 1d | donchian_breakout | 3970 | -0.032 | 2441 | -0.065 | 2017-03-15 |
| 1d | mean_reversion | 1734 | -0.152 | 1509 | -0.113 | 2017-03-15 |
| 1d | trend_pullback | 2761 | -0.025 | 1693 | -0.064 | 2017-03-15 |
| 1h | donchian_breakout | 5412 | -0.105 | 3141 | -0.194 | 2025-12-10 |
| 1h | mean_reversion | 2309 | -0.194 | 1837 | -0.102 | 2025-12-10 |
| 1h | trend_pullback | 3068 | -0.178 | 2217 | -0.121 | 2025-12-10 |
| 4h | donchian_breakout | 1256 | +0.009 | 680 | -0.174 | 2026-03-02 |
| 4h | mean_reversion | 523 | -0.229 | 457 | -0.092 | 2026-03-02 |
| 4h | trend_pullback | 704 | +0.040 | 519 | -0.259 | 2026-03-02 |

Filtrów z wystarczającą próbą: 313. Kandydatów na próbie odkrywczej: 5 (z samego przypadku spodziewane ok. 8). Potwierdzonych na próbie niewidzianej: 1 (z samego przypadku spodziewane ok. 0.2).

### Kandydaci i ich wynik na próbie potwierdzającej

| Int. | Strategia | Zakres | Cecha = wartość | Odkr.: n | Odkr.: śr. R | Odkr.: t | Potw.: n | Potw.: śr. R | Potw.: t | Wynik |
|---|---|---|---|---|---|---|---|---|---|---|
| 1d | donchian_breakout | stocks | vol = niska | 529 | +0.205 | 2.4 | 499 | +0.186 | 2.0 | POTWIERDZONY |
| 4h | donchian_breakout | crypto | d1_trend = zgodny | 488 | +0.154 | 2.1 | 49 | +0.284 | 1.2 | za mała próba |
| 4h | donchian_breakout | wszystkie | vol = niska | 362 | +0.186 | 2.1 | 192 | -0.121 | -1.1 | nie utrzymał się |
| 4h | donchian_breakout | crypto | vol = niska | 262 | +0.277 | 2.7 | 26 | -0.560 | -2.1 | za mała próba |
| 4h | trend_pullback | wszystkie | session = usa | 253 | +0.193 | 2.3 | 224 | -0.299 | -3.8 | nie utrzymał się |
