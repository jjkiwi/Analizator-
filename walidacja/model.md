# Model przewidywań (H5): raport walidacji

Przeliczono: 2026-11-21T11:45:49+00:00. Dane: 2000-12-12 – 2026-11-20, 70 instrumentów, 333460 wierszy (dzień × instrument).

Regresja logistyczna z karą L2, cechy przyczynowe na zamknięciu dnia, cel: czy cena za h sesji będzie wyższa. Poziom bazowy: częstość wzrostów instrumentu w danych treningowych. Brier skill (BSS) > 0 oznacza lepiej niż baza.

Kryterium (zapisane przed testem): na teście Brier < bazy z p < 0.025 (bootstrap blokowy), dodatni przyrost log loss, średni BSS walk-forward > 0, model na przetasowanych celach BSS ≤ 0.002.

## Horyzont 5 sesji: NIE PRZESZEDŁ (jakość: brak)

Podział: trening do 2019-07-16 (209002 wierszy), walidacja od 2019-07-16 (49767), test 2022-09-07 – 2026-11-15 (72903); embargo 10 dni. Wybrane C = 0.01.

| Zbiór | n | Brier | Brier bazy | BSS | log loss | log loss bazy | AUC | trafność | wzrosty |
|---|---|---|---|---|---|---|---|---|---|
| test | 72903 | 0.2487 | 0.2498 | 0.0041 | 0.6906 | 0.6929 | 0.531 | 0.529 | 0.530 |
| WF 2010-04-27–2013-02-14 | 33217 | 0.2513 | 0.2501 | -0.0045 | 0.6957 | 0.6934 | 0.502 | 0.506 | 0.516 |
| WF 2013-02-15–2015-12-08 | 38561 | 0.2495 | 0.2513 | 0.0069 | 0.6922 | 0.6957 | 0.530 | 0.525 | 0.497 |
| WF 2015-12-09–2018-08-16 | 37174 | 0.2488 | 0.2484 | -0.0015 | 0.6907 | 0.6903 | 0.534 | 0.527 | 0.519 |
| WF 2018-08-17–2020-08-18 | 30891 | 0.2497 | 0.2493 | -0.0017 | 0.6926 | 0.6923 | 0.530 | 0.526 | 0.523 |
| WF 2020-08-19–2022-08-22 | 32685 | 0.2485 | 0.2492 | 0.0030 | 0.6901 | 0.6918 | 0.543 | 0.533 | 0.511 |

Bootstrap blokowy (blok 20 dni, 2000 losowań): p (Brier) = 0.421, p (log loss) = 0.397. Średni BSS walk-forward: 0.0004. Test przecieku (przetasowane cele): BSS = 0.0015 (OK).

Wynik per kategoria (test):

| Kategoria | n | BSS | AUC | trafność |
|---|---|---|---|---|
| crypto | 4593 | -0.0065 | 0.497 | 0.513 |
| indices | 17143 | -0.0002 | 0.506 | 0.567 |
| metals | 4220 | 0.0075 | 0.574 | 0.543 |
| stocks | 46947 | 0.0064 | 0.526 | 0.516 |

Kalibracja (test, przedziały kwantylowe prognozy):

| średnia prognoza | zaobserwowana częstość | n |
|---|---|---|
| 0.451 | 0.480 | 7291 |
| 0.476 | 0.513 | 7290 |
| 0.490 | 0.514 | 7290 |
| 0.501 | 0.499 | 7290 |
| 0.510 | 0.522 | 7290 |
| 0.518 | 0.532 | 7291 |
| 0.528 | 0.555 | 7290 |
| 0.542 | 0.557 | 7290 |
| 0.557 | 0.562 | 7290 |
| 0.570 | 0.569 | 7291 |

Najsilniejsze współczynniki (skala standaryzowana, średnia z okien walk-forward):

| cecha | średnia | odch. std | zgodność znaku |
|---|---|---|---|
| dist_sma200_atr | 0.164 | 0.112 | 100% |
| ret_60 | -0.095 | 0.044 | 100% |
| vol_60 | -0.081 | 0.023 | 100% |
| rel_mkt_20 | -0.079 | 0.033 | 100% |
| ret_5 | -0.075 | 0.010 | 100% |
| rsi_14 | 0.070 | 0.022 | 100% |
| trend_12m | 0.069 | 0.011 | 100% |
| rel_mkt_60 | 0.060 | 0.050 | 80% |

## Horyzont 20 sesji: NIE PRZESZEDŁ (jakość: brak)

Podział: trening do 2019-07-07 (206823 wierszy), walidacja od 2019-07-07 (47560), test 2022-08-26 – 2026-10-31 (72374); embargo 31 dni. Wybrane C = 0.01.

| Zbiór | n | Brier | Brier bazy | BSS | log loss | log loss bazy | AUC | trafność | wzrosty |
|---|---|---|---|---|---|---|---|---|---|
| test | 72374 | 0.2465 | 0.2477 | 0.0049 | 0.6861 | 0.6886 | 0.526 | 0.550 | 0.563 |
| WF 2010-03-31–2013-01-10 | 32777 | 0.2534 | 0.2491 | -0.0173 | 0.7001 | 0.6914 | 0.488 | 0.510 | 0.534 |
| WF 2013-01-11–2015-10-26 | 38118 | 0.2514 | 0.2524 | 0.0042 | 0.6962 | 0.6981 | 0.509 | 0.535 | 0.525 |
| WF 2015-10-27–2018-07-11 | 37308 | 0.2488 | 0.2479 | -0.0035 | 0.6907 | 0.6891 | 0.525 | 0.542 | 0.537 |
| WF 2018-07-12–2020-07-07 | 30595 | 0.2547 | 0.2488 | -0.0236 | 0.7040 | 0.6911 | 0.491 | 0.515 | 0.546 |
| WF 2020-07-08–2022-07-05 | 31940 | 0.2481 | 0.2498 | 0.0069 | 0.6894 | 0.6929 | 0.550 | 0.536 | 0.516 |

Bootstrap blokowy (blok 40 dni, 2000 losowań): p (Brier) = 0.454, p (log loss) = 0.464. Średni BSS walk-forward: -0.0067. Test przecieku (przetasowane cele): BSS = 0.0048 (NIE).

Wynik per kategoria (test):

| Kategoria | n | BSS | AUC | trafność |
|---|---|---|---|---|
| crypto | 4584 | -0.0086 | 0.457 | 0.481 |
| indices | 17010 | -0.0060 | 0.479 | 0.606 |
| metals | 4188 | 0.0151 | 0.578 | 0.570 |
| stocks | 46592 | 0.0092 | 0.515 | 0.535 |

Kalibracja (test, przedziały kwantylowe prognozy):

| średnia prognoza | zaobserwowana częstość | n |
|---|---|---|
| 0.464 | 0.512 | 7238 |
| 0.490 | 0.550 | 7237 |
| 0.508 | 0.551 | 7237 |
| 0.523 | 0.567 | 7238 |
| 0.535 | 0.547 | 7237 |
| 0.544 | 0.556 | 7237 |
| 0.553 | 0.558 | 7238 |
| 0.565 | 0.587 | 7237 |
| 0.585 | 0.613 | 7237 |
| 0.603 | 0.587 | 7238 |

Najsilniejsze współczynniki (skala standaryzowana, średnia z okien walk-forward):

| cecha | średnia | odch. std | zgodność znaku |
|---|---|---|---|
| dist_sma50_atr | -0.179 | 0.041 | 100% |
| rsi_14 | 0.162 | 0.025 | 100% |
| dist_sma200_atr | 0.109 | 0.029 | 100% |
| trend_12m | 0.103 | 0.021 | 100% |
| rel_mkt_20 | -0.088 | 0.061 | 100% |
| ret_250 | -0.082 | 0.049 | 100% |
| ret_20 | 0.057 | 0.069 | 60% |
| cat_crypto | -0.054 | 0.093 | 40% |

Prognozy modelu to prawdopodobieństwa, nie rekomendacje. Jakość „brak” oznacza, że model nie jest lepszy od samej częstości wzrostów i jego prognozy nie niosą informacji.
