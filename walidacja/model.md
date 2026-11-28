# Model przewidywań (H5): raport walidacji

Przeliczono: 2026-11-28T12:43:03+00:00. Dane: 2000-12-12 – 2026-11-27, 70 instrumentów, 333815 wierszy (dzień × instrument).

Regresja logistyczna z karą L2, cechy przyczynowe na zamknięciu dnia, cel: czy cena za h sesji będzie wyższa. Poziom bazowy: częstość wzrostów instrumentu w danych treningowych. Brier skill (BSS) > 0 oznacza lepiej niż baza.

Kryterium (zapisane przed testem): na teście Brier < bazy z p < 0.025 (bootstrap blokowy), dodatni przyrost log loss, średni BSS walk-forward > 0, model na przetasowanych celach BSS ≤ 0.002.

## Horyzont 5 sesji: NIE PRZESZEDŁ (jakość: brak)

Podział: trening do 2019-07-21 (209183 wierszy), walidacja od 2019-07-21 (49793), test 2022-09-12 – 2026-11-22 (73054); embargo 10 dni. Wybrane C = 0.01.

| Zbiór | n | Brier | Brier bazy | BSS | log loss | log loss bazy | AUC | trafność | wzrosty |
|---|---|---|---|---|---|---|---|---|---|
| test | 73054 | 0.2488 | 0.2498 | 0.0039 | 0.6908 | 0.6929 | 0.530 | 0.529 | 0.529 |
| WF 2010-04-29–2013-02-18 | 33222 | 0.2512 | 0.2501 | -0.0044 | 0.6955 | 0.6933 | 0.502 | 0.506 | 0.517 |
| WF 2013-02-19–2015-12-11 | 38632 | 0.2495 | 0.2512 | 0.0069 | 0.6922 | 0.6956 | 0.530 | 0.525 | 0.498 |
| WF 2015-12-14–2018-08-20 | 37132 | 0.2487 | 0.2483 | -0.0017 | 0.6906 | 0.6901 | 0.535 | 0.528 | 0.519 |
| WF 2018-08-21–2020-08-23 | 30955 | 0.2499 | 0.2493 | -0.0023 | 0.6929 | 0.6923 | 0.530 | 0.527 | 0.523 |
| WF 2020-08-24–2022-08-27 | 32765 | 0.2485 | 0.2494 | 0.0035 | 0.6902 | 0.6922 | 0.544 | 0.533 | 0.508 |

Bootstrap blokowy (blok 20 dni, 2000 losowań): p (Brier) = 0.429, p (log loss) = 0.410. Średni BSS walk-forward: 0.0004. Test przecieku (przetasowane cele): BSS = 0.0017 (OK).

Wynik per kategoria (test):

| Kategoria | n | BSS | AUC | trafność |
|---|---|---|---|---|
| crypto | 4599 | -0.0070 | 0.495 | 0.512 |
| indices | 17184 | -0.0006 | 0.503 | 0.566 |
| metals | 4232 | 0.0077 | 0.576 | 0.542 |
| stocks | 47039 | 0.0063 | 0.525 | 0.515 |

Kalibracja (test, przedziały kwantylowe prognozy):

| średnia prognoza | zaobserwowana częstość | n |
|---|---|---|
| 0.451 | 0.481 | 7306 |
| 0.476 | 0.514 | 7305 |
| 0.490 | 0.511 | 7305 |
| 0.501 | 0.500 | 7306 |
| 0.509 | 0.522 | 7305 |
| 0.518 | 0.529 | 7305 |
| 0.527 | 0.551 | 7306 |
| 0.542 | 0.559 | 7305 |
| 0.557 | 0.562 | 7305 |
| 0.570 | 0.566 | 7306 |

Najsilniejsze współczynniki (skala standaryzowana, średnia z okien walk-forward):

| cecha | średnia | odch. std | zgodność znaku |
|---|---|---|---|
| dist_sma200_atr | 0.163 | 0.113 | 100% |
| ret_60 | -0.094 | 0.043 | 100% |
| vol_60 | -0.081 | 0.022 | 100% |
| rel_mkt_20 | -0.079 | 0.033 | 100% |
| ret_5 | -0.075 | 0.010 | 100% |
| rsi_14 | 0.069 | 0.022 | 100% |
| trend_12m | 0.069 | 0.011 | 100% |
| rel_mkt_60 | 0.060 | 0.049 | 80% |

## Horyzont 20 sesji: NIE PRZESZEDŁ (jakość: brak)

Podział: trening do 2019-07-11 (206944 wierszy), walidacja od 2019-07-11 (47648), test 2022-08-31 – 2026-11-07 (72528); embargo 31 dni. Wybrane C = 0.01.

| Zbiór | n | Brier | Brier bazy | BSS | log loss | log loss bazy | AUC | trafność | wzrosty |
|---|---|---|---|---|---|---|---|---|---|
| test | 72528 | 0.2466 | 0.2477 | 0.0043 | 0.6863 | 0.6885 | 0.525 | 0.549 | 0.562 |
| WF 2010-04-02–2013-01-15 | 32846 | 0.2534 | 0.2491 | -0.0172 | 0.7001 | 0.6914 | 0.488 | 0.511 | 0.535 |
| WF 2013-01-16–2015-10-30 | 38179 | 0.2512 | 0.2524 | 0.0048 | 0.6960 | 0.6981 | 0.512 | 0.536 | 0.524 |
| WF 2015-11-02–2018-07-15 | 37212 | 0.2489 | 0.2478 | -0.0043 | 0.6909 | 0.6889 | 0.522 | 0.541 | 0.538 |
| WF 2018-07-16–2020-07-12 | 30659 | 0.2554 | 0.2489 | -0.0260 | 0.7059 | 0.6913 | 0.492 | 0.516 | 0.546 |
| WF 2020-07-13–2022-07-10 | 32023 | 0.2483 | 0.2496 | 0.0055 | 0.6897 | 0.6925 | 0.549 | 0.534 | 0.516 |

Bootstrap blokowy (blok 40 dni, 2000 losowań): p (Brier) = 0.524, p (log loss) = 0.538. Średni BSS walk-forward: -0.0074. Test przecieku (przetasowane cele): BSS = 0.0041 (NIE).

Wynik per kategoria (test):

| Kategoria | n | BSS | AUC | trafność |
|---|---|---|---|---|
| crypto | 4590 | -0.0111 | 0.453 | 0.477 |
| indices | 17052 | -0.0066 | 0.474 | 0.605 |
| metals | 4200 | 0.0151 | 0.578 | 0.567 |
| stocks | 46686 | 0.0087 | 0.515 | 0.535 |

Kalibracja (test, przedziały kwantylowe prognozy):

| średnia prognoza | zaobserwowana częstość | n |
|---|---|---|
| 0.465 | 0.511 | 7253 |
| 0.490 | 0.552 | 7253 |
| 0.509 | 0.553 | 7253 |
| 0.524 | 0.567 | 7252 |
| 0.536 | 0.547 | 7253 |
| 0.544 | 0.553 | 7253 |
| 0.553 | 0.560 | 7252 |
| 0.565 | 0.585 | 7253 |
| 0.585 | 0.611 | 7253 |
| 0.603 | 0.583 | 7253 |

Najsilniejsze współczynniki (skala standaryzowana, średnia z okien walk-forward):

| cecha | średnia | odch. std | zgodność znaku |
|---|---|---|---|
| dist_sma50_atr | -0.178 | 0.042 | 100% |
| rsi_14 | 0.161 | 0.026 | 100% |
| dist_sma200_atr | 0.109 | 0.029 | 100% |
| trend_12m | 0.103 | 0.021 | 100% |
| rel_mkt_20 | -0.089 | 0.059 | 100% |
| ret_250 | -0.082 | 0.049 | 100% |
| cat_crypto | -0.059 | 0.103 | 40% |
| ret_20 | 0.058 | 0.067 | 80% |

Prognozy modelu to prawdopodobieństwa, nie rekomendacje. Jakość „brak” oznacza, że model nie jest lepszy od samej częstości wzrostów i jego prognozy nie niosą informacji.
