# Model przewidywań (H5): raport walidacji

Przeliczono: 2026-11-17T23:37:54+00:00. Dane: 2000-12-12 – 2026-11-12, 52 instrumentów, 240028 wierszy (dzień × instrument).

Regresja logistyczna z karą L2, cechy przyczynowe na zamknięciu dnia, cel: czy cena za h sesji będzie wyższa. Poziom bazowy: częstość wzrostów instrumentu w danych treningowych. Brier skill (BSS) > 0 oznacza lepiej niż baza.

Kryterium (zapisane przed testem): na teście Brier < bazy z p < 0.025 (bootstrap blokowy), dodatni przyrost log loss, średni BSS walk-forward > 0, model na przetasowanych celach BSS ≤ 0.002.

## Horyzont 5 sesji: NIE PRZESZEDŁ (jakość: brak)

Podział: trening do 2019-07-11 (147995 wierszy), walidacja od 2019-07-11 (36749), test 2022-08-31 – 2026-11-07 (53893); embargo 10 dni. Wybrane C = 0.01.

| Zbiór | n | Brier | Brier bazy | BSS | log loss | log loss bazy | AUC | trafność | wzrosty |
|---|---|---|---|---|---|---|---|---|---|
| test | 53893 | 0.2487 | 0.2496 | 0.0037 | 0.6905 | 0.6926 | 0.534 | 0.533 | 0.528 |
| WF 2010-04-22–2013-02-08 | 23197 | 0.2508 | 0.2502 | -0.0023 | 0.6948 | 0.6936 | 0.514 | 0.514 | 0.520 |
| WF 2013-02-11–2015-12-01 | 27025 | 0.2489 | 0.2514 | 0.0100 | 0.6910 | 0.6960 | 0.536 | 0.529 | 0.498 |
| WF 2015-12-02–2018-08-11 | 26213 | 0.2489 | 0.2480 | -0.0033 | 0.6909 | 0.6898 | 0.533 | 0.527 | 0.522 |
| WF 2018-08-12–2020-08-12 | 22531 | 0.2495 | 0.2490 | -0.0017 | 0.6922 | 0.6920 | 0.530 | 0.533 | 0.537 |
| WF 2020-08-13–2022-08-15 | 24282 | 0.2481 | 0.2486 | 0.0020 | 0.6893 | 0.6906 | 0.546 | 0.540 | 0.516 |

Bootstrap blokowy (blok 20 dni, 2000 losowań): p (Brier) = 0.712, p (log loss) = 0.686. Średni BSS walk-forward: 0.0009. Test przecieku (przetasowane cele): BSS = 0.0006 (OK).

Wynik per kategoria (test):

| Kategoria | n | BSS | AUC | trafność |
|---|---|---|---|---|
| crypto | 4590 | -0.0074 | 0.500 | 0.510 |
| indices | 17097 | -0.0016 | 0.498 | 0.569 |
| metals | 4204 | 0.0066 | 0.564 | 0.546 |
| stocks | 28002 | 0.0082 | 0.521 | 0.514 |

Kalibracja (test, przedziały kwantylowe prognozy):

| średnia prognoza | zaobserwowana częstość | n |
|---|---|---|
| 0.441 | 0.474 | 5390 |
| 0.470 | 0.501 | 5389 |
| 0.487 | 0.503 | 5389 |
| 0.501 | 0.499 | 5389 |
| 0.512 | 0.528 | 5389 |
| 0.524 | 0.532 | 5390 |
| 0.539 | 0.561 | 5389 |
| 0.554 | 0.560 | 5389 |
| 0.565 | 0.561 | 5389 |
| 0.576 | 0.562 | 5390 |

Najsilniejsze współczynniki (skala standaryzowana, średnia z okien walk-forward):

| cecha | średnia | odch. std | zgodność znaku |
|---|---|---|---|
| dist_sma200_atr | 0.139 | 0.116 | 80% |
| rsi_14 | 0.117 | 0.029 | 100% |
| vol_60 | -0.112 | 0.024 | 100% |
| ret_60 | -0.107 | 0.037 | 100% |
| ret_5 | -0.091 | 0.011 | 100% |
| trend_12m | 0.089 | 0.016 | 100% |
| vol_20 | 0.077 | 0.025 | 100% |
| rel_mkt_60 | 0.076 | 0.051 | 80% |

## Horyzont 20 sesji: NIE PRZESZEDŁ (jakość: brak)

Podział: trening do 2019-07-01 (146432 wierszy), walidacja od 2019-07-01 (35202), test 2022-08-19 – 2026-10-23 (53506); embargo 31 dni. Wybrane C = 0.01.

| Zbiór | n | Brier | Brier bazy | BSS | log loss | log loss bazy | AUC | trafność | wzrosty |
|---|---|---|---|---|---|---|---|---|---|
| test | 53506 | 0.2466 | 0.2479 | 0.0054 | 0.6862 | 0.6890 | 0.533 | 0.550 | 0.557 |
| WF 2010-03-26–2013-01-04 | 22856 | 0.2528 | 0.2484 | -0.0180 | 0.6990 | 0.6899 | 0.492 | 0.518 | 0.544 |
| WF 2013-01-07–2015-10-20 | 26791 | 0.2521 | 0.2529 | 0.0029 | 0.6979 | 0.6990 | 0.506 | 0.540 | 0.521 |
| WF 2015-10-21–2018-07-05 | 26228 | 0.2488 | 0.2466 | -0.0088 | 0.6908 | 0.6865 | 0.518 | 0.544 | 0.548 |
| WF 2018-07-06–2020-07-01 | 22313 | 0.2538 | 0.2473 | -0.0262 | 0.7016 | 0.6882 | 0.483 | 0.529 | 0.568 |
| WF 2020-07-02–2022-06-28 | 23729 | 0.2480 | 0.2501 | 0.0085 | 0.6891 | 0.6934 | 0.555 | 0.542 | 0.513 |

Bootstrap blokowy (blok 40 dni, 2000 losowań): p (Brier) = 0.523, p (log loss) = 0.516. Średni BSS walk-forward: -0.0083. Test przecieku (przetasowane cele): BSS = 0.0032 (NIE).

Wynik per kategoria (test):

| Kategoria | n | BSS | AUC | trafność |
|---|---|---|---|---|
| crypto | 4581 | -0.0074 | 0.464 | 0.485 |
| indices | 16969 | -0.0070 | 0.479 | 0.605 |
| metals | 4176 | 0.0167 | 0.582 | 0.573 |
| stocks | 27780 | 0.0131 | 0.517 | 0.524 |

Kalibracja (test, przedziały kwantylowe prognozy):

| średnia prognoza | zaobserwowana częstość | n |
|---|---|---|
| 0.455 | 0.499 | 5351 |
| 0.484 | 0.527 | 5350 |
| 0.505 | 0.542 | 5351 |
| 0.522 | 0.549 | 5350 |
| 0.535 | 0.554 | 5351 |
| 0.547 | 0.546 | 5350 |
| 0.560 | 0.564 | 5351 |
| 0.577 | 0.612 | 5350 |
| 0.593 | 0.601 | 5351 |
| 0.608 | 0.580 | 5351 |

Najsilniejsze współczynniki (skala standaryzowana, średnia z okien walk-forward):

| cecha | średnia | odch. std | zgodność znaku |
|---|---|---|---|
| rsi_14 | 0.215 | 0.037 | 100% |
| dist_sma50_atr | -0.211 | 0.046 | 100% |
| trend_12m | 0.117 | 0.029 | 100% |
| ret_250 | -0.115 | 0.059 | 100% |
| rel_mkt_20 | -0.097 | 0.056 | 100% |
| dist_sma200_atr | 0.088 | 0.034 | 100% |
| vol_60 | -0.063 | 0.033 | 100% |
| vol_20 | 0.057 | 0.036 | 80% |

Prognozy modelu to prawdopodobieństwa, nie rekomendacje. Jakość „brak” oznacza, że model nie jest lepszy od samej częstości wzrostów i jego prognozy nie niosą informacji.
