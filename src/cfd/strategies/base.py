from __future__ import annotations

from typing import Protocol

import pandas as pd


class Strategy(Protocol):
    """Strategia zwraca ramke o tym samym indeksie co swiece, z kolumnami:

    side      +1 long, -1 short, 0 brak sygnalu (na zamknieciu danej swiecy)
    sl_dist   odleglosc stop lossa od ceny wejscia (w jednostkach ceny, > 0)
    tp_dist   odleglosc take profitu od ceny wejscia
    rationale krotkie uzasadnienie tekstowe

    Wiersz i moze korzystac wylacznie z danych do swiecy i wlacznie.
    """

    name: str

    def generate(self, df: pd.DataFrame) -> pd.DataFrame: ...
