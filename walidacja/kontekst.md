### Punkt odniesienia (wszystkie sygnaly, bez filtra)

| Interwał | Strategia | Odkrywcza: n | Odkrywcza: śr. R | Potwierdzająca: n | Potwierdzająca: śr. R | Granica prób |
|---|---|---|---|---|---|---|
| 1d | donchian_breakout | 3268 | -0.033 | 1932 | -0.090 | 2016-10-14 |
| 1d | mean_reversion | 1404 | -0.108 | 1268 | -0.135 | 2016-10-14 |
| 1d | trend_pullback | 2252 | -0.010 | 1418 | -0.083 | 2016-10-14 |
| 1h | donchian_breakout | 4830 | -0.108 | 2771 | -0.202 | 2025-11-12 |
| 1h | mean_reversion | 2032 | -0.214 | 1690 | -0.093 | 2025-11-12 |
| 1h | trend_pullback | 2728 | -0.173 | 1935 | -0.148 | 2025-11-12 |
| 4h | donchian_breakout | 1120 | +0.006 | 593 | -0.151 | 2026-01-20 |
| 4h | mean_reversion | 428 | -0.210 | 407 | -0.080 | 2026-01-20 |
| 4h | trend_pullback | 629 | +0.025 | 455 | -0.208 | 2026-01-20 |

Filtrów z wystarczającą próbą: 276. Kandydatów na próbie odkrywczej: 4 (z samego przypadku spodziewane ok. 7). Potwierdzonych na próbie niewidzianej: 0 (z samego przypadku spodziewane ok. 0.2).

### Kandydaci i ich wynik na próbie potwierdzającej

| Int. | Strategia | Zakres | Cecha = wartość | Odkr.: n | Odkr.: śr. R | Odkr.: t | Potw.: n | Potw.: śr. R | Potw.: t | Wynik |
|---|---|---|---|---|---|---|---|---|---|---|
| 1d | donchian_breakout | stocks | vol = niska | 277 | +0.326 | 2.5 | 290 | +0.140 | 1.0 | nie utrzymał się |
| 4h | donchian_breakout | wszystkie | vol = niska | 345 | +0.185 | 2.1 | 146 | -0.114 | -0.9 | nie utrzymał się |
| 4h | donchian_breakout | crypto | vol = niska | 262 | +0.277 | 2.7 | 24 | -0.613 | -2.2 | za mała próba |
| 4h | trend_pullback | wszystkie | session = usa | 225 | +0.190 | 2.1 | 175 | -0.226 | -2.5 | nie utrzymał się |
