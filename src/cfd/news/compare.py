"""Porownanie klasyfikatora regulowego z LLM na newsach z bazy (zadanie C3).

Uzycie (wymaga ANTHROPIC_API_KEY w srodowisku i pakietu `anthropic`):
    python -m cfd.news.compare [--limit 50] [--min-importance 3] [--data-dir data] [--config-dir config]

Bierze ostatnie newsy, ktore w bazie maja wage >= --min-importance, klasyfikuje je ponownie regulami
i LLM-em, wypisuje tabele, zgodnosc wag oraz zuzycie tokenow i koszt. Niczego nie zapisuje do bazy.
"""
from __future__ import annotations

import argparse
import os
import sys
from collections import Counter
from pathlib import Path

from ..db import connect
from .classify import LLMClassifier, RuleClassifier
from .mapper import KeywordMapper
from .models import NewsItem


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--min-importance", type=int, default=3)
    ap.add_argument("--data-dir", default="data")
    ap.add_argument("--config-dir", default="config")
    args = ap.parse_args(argv)
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("Brak ANTHROPIC_API_KEY: porownanie wymaga klucza (wpisz go do .env i zaladuj do srodowiska).")
        return 2
    conn = connect(Path(args.data_dir) / "cfd.sqlite")
    mapper = KeywordMapper.from_file(Path(args.config_dir) / "keywords.yaml")
    rules, llm = RuleClassifier(), LLMClassifier()
    rows = conn.execute(
        "SELECT source, title, summary, url FROM news WHERE importance >= ? ORDER BY fetched DESC LIMIT ?",
        (args.min_importance, args.limit)).fetchall()
    pairs: Counter = Counter()
    failed = 0
    for r in rows:
        item = NewsItem(r["source"], r["title"], r["url"] or "", r["summary"] or "")
        match = mapper.match(item.text, item.title)
        if not match["symbols"]:
            continue
        a, b = rules.classify(item, match), llm.classify(item, match)
        if b.classifier != "llm":
            failed += 1
            continue
        pairs[(a.importance, b.importance)] += 1
        print(f"reguly {a.importance} | LLM {b.importance} | {item.title[:80]} | {b.reason[:90]}")
    n = sum(pairs.values())
    if not n:
        print(f"Brak porownan (nieudanych wywolan LLM: {failed}).")
        return 1
    print(f"\nPorownanych: {n}, nieudanych wywolan LLM: {failed}")
    print(f"Zgodna waga: {sum(v for (x, y), v in pairs.items() if x == y)} z {n}")
    for (x, y), v in sorted(pairs.items()):
        print(f"  reguly {x} -> LLM {y}: {v}")
    print(f"Tokeny: wejscie {llm.input_tokens}, wyjscie {llm.output_tokens} "
          f"(srednio {llm.input_tokens / llm.calls:.0f} / {llm.output_tokens / llm.calls:.0f} na news)")
    print(f"Koszt wg cennika Haiku 5.5: {llm.cost_usd:.4f} USD, czyli {llm.cost_usd / llm.calls * 1000:.3f} USD za 1000 newsow")
    return 0


if __name__ == "__main__":
    sys.exit(main())
