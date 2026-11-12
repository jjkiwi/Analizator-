### Punkt odniesienia (wszystkie sygnaly, bez filtra)

| Interwał | Strategia | Odkrywcza: n | Odkrywcza: śr. R | Potwierdzająca: n | Potwierdzająca: śr. R | Granica prób |
|---|---|---|---|---|---|---|
| 1d | donchian_breakout | 3268 | -0.033 | 1929 | -0.088 | 2016-10-09 |
| 1d | mean_reversion | 1402 | -0.109 | 1270 | -0.134 | 2016-10-09 |
| 1d | trend_pullback | 2250 | -0.012 | 1415 | -0.079 | 2016-10-09 |
| 1h | donchian_breakout | 4790 | -0.118 | 2741 | -0.195 | 2025-11-11 |
| 1h | mean_reversion | 2029 | -0.214 | 1650 | -0.088 | 2025-11-11 |
| 1h | trend_pullback | 2706 | -0.174 | 1960 | -0.133 | 2025-11-11 |
| 4h | donchian_breakout | 1111 | +0.003 | 581 | -0.135 | 2026-01-15 |
| 4h | mean_reversion | 425 | -0.197 | 413 | -0.108 | 2026-01-15 |
| 4h | trend_pullback | 624 | +0.009 | 447 | -0.194 | 2026-01-15 |

Filtrów z wystarczającą próbą: 276. Kandydatów na próbie odkrywczej: 3 (z samego przypadku spodziewane ok. 7). Potwierdzonych na próbie niewidzianej: 0 (z samego przypadku spodziewane ok. 0.2).

### Kandydaci i ich wynik na próbie potwierdzającej

| Int. | Strategia | Zakres | Cecha = wartość | Odkr.: n | Odkr.: śr. R | Odkr.: t | Potw.: n | Potw.: śr. R | Potw.: t | Wynik |
|---|---|---|---|---|---|---|---|---|---|---|
| 1d | donchian_breakout | stocks | vol = niska | 277 | +0.326 | 2.5 | 289 | +0.144 | 1.1 | nie utrzymał się |
| 4h | donchian_breakout | crypto | vol = niska | 262 | +0.277 | 2.7 | 24 | -0.613 | -2.2 | za mała próba |
| 4h | trend_pullback | wszystkie | session = usa | 226 | +0.193 | 2.2 | 169 | -0.204 | -2.2 | nie utrzymał się |
