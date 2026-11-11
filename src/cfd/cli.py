from __future__ import annotations

import argparse
import logging
import os
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

from . import journal
from .backtest import run_backtest, summarize
from .data import CandleStore, DataService, DataSourceError, default_adapters
from .db import connect
from .instruments import load_instruments
from .scanner import latest_signal
from .settings import load_dotenv, load_settings
from .strategies import PARAM_GRIDS, REGISTRY

STRATS = sorted(REGISTRY)


def _cfg(args, name: str) -> Path:
    return Path(args.config_dir) / name


def _instruments(args) -> dict:
    return load_instruments(_cfg(args, "instruments.yaml"))


def _service(args) -> DataService:
    return DataService(default_adapters(), CandleStore(Path(args.data_dir) / "candles"))


def _conn(args):
    return connect(Path(args.data_dir) / "cfd.sqlite")


def _pick(instruments: dict, symbols, category) -> list:
    if symbols:
        missing = [s for s in symbols if s not in instruments]
        if missing:
            sys.exit(f"Nieznane symbole: {missing}")
        return [instruments[s] for s in symbols]
    return [i for i in instruments.values() if category in (None, i.category)]


def _context(args):
    """Sklada wszystko, czego potrzebuje praca ciagla. Brakujace klucze = dana czesc jest wylaczona."""
    from .fundamentals import FredClient, load_components
    from .macro import FairEconomyCalendar, MacroRules
    from .news import ChainClassifier, KeywordMapper, RuleClassifier, load_feeds
    from .notify import QuietNotifier, notifier_from_env
    from .runner import Context

    instruments = _instruments(args)
    settings = load_settings(_cfg(args, "settings.yaml"))
    conn = _conn(args)
    rules = RuleClassifier()
    chain = ChainClassifier.from_file(_cfg(args, "llm.yaml"), fallback=rules) if settings["news"]["use_llm"] else None
    use_llm = bool(chain and chain.providers)
    fred = FredClient() if os.environ.get("FRED_API_KEY") else None
    q = settings["quiet_hours"]
    return Context(
        conn=conn, settings=settings, instruments=instruments, data=_service(args),
        notifier=QuietNotifier(notifier_from_env(), conn, q["start"], q["end"], q["tz"]),
        feeds=load_feeds(_cfg(args, "feeds.yaml")),
        mapper=KeywordMapper.from_file(_cfg(args, "keywords.yaml"), set(instruments)),
        classifier=chain if use_llm else rules,
        cheap_classifier=rules if use_llm else None,
        macro_source=FairEconomyCalendar(), macro_rules=MacroRules.from_file(_cfg(args, "macro_rules.yaml")),
        fund_components=load_components(_cfg(args, "fundamentals.yaml")),
        fund_series=fred.series if fred else None,
    )


# ---------- dane ----------

def cmd_instruments(args) -> None:
    for inst in _pick(_instruments(args), None, args.category):
        src = ", ".join(f"{k}:{v}" for k, v in inst.sources.items()) or "BRAK ZRODLA"
        print(f"{inst.symbol:<10} {inst.category:<12} {inst.name:<18} {src}")


def cmd_check_sources(args) -> None:
    adapters = default_adapters()
    ok = bad = 0
    since = pd.Timestamp.now(tz="UTC") - pd.Timedelta(days=30)
    for inst in _pick(_instruments(args), args.symbols, args.category):
        if not inst.sources:
            print(f"{inst.symbol:<10} --       BRAK ZRODLA")
            bad += 1
            continue
        for name, src_symbol in inst.sources.items():
            try:
                df = adapters[name].fetch(src_symbol, "1d", since.to_pydatetime())
                print(f"{inst.symbol:<10} {name:<8} OK    {src_symbol:<12} ostatnia swieca {df.index[-1].date()} close {df['close'].iloc[-1]:.6g}")
                ok += 1
            except (DataSourceError, KeyError) as exc:
                print(f"{inst.symbol:<10} {name:<8} BLAD  {src_symbol:<12} {str(exc)[:110]}")
                bad += 1
    print(f"\nDziala: {ok}, nie dziala: {bad}")


def cmd_fetch(args) -> None:
    svc = _service(args)
    for inst in _pick(_instruments(args), args.symbols, args.category):
        try:
            df, source = svc.update(inst, args.interval)
            print(f"{inst.symbol:<10} {source:<8} {len(df):>6} swiec  {df.index[0].date()} -> {df.index[-1].date()}")
        except DataSourceError as exc:
            print(f"{inst.symbol:<10} BLAD: {str(exc)[:140]}")


# ---------- analiza ----------

def _print_stats(label: str, st: dict) -> None:
    if not st.get("trades"):
        print(f"{label}: brak transakcji")
        return
    print(f"{label}: transakcji {st['trades']}, skutecznosc {st['win_rate']:.0%}, oczekiwana {st['expectancy_r']:+.2f}R, "
          f"PF {st['profit_factor']:.2f}, suma {st['total_r']:+.1f}R (koszty {st['costs_total_r']:.1f}R), max DD {st['max_drawdown_pct']:.1f}%")


def cmd_backtest(args) -> None:
    svc, strategy = _service(args), REGISTRY[args.strategy]()
    for inst in _pick(_instruments(args), args.symbols, args.category):
        try:
            df = svc.get(inst, args.interval, refresh=args.refresh)
        except DataSourceError as exc:
            print(f"{inst.symbol}: {exc}")
            continue
        trades = run_backtest(df, strategy.generate(df), inst.costs, max_bars=args.max_bars)
        cut = df.index[int(len(df) * args.split)]
        print(f"\n== {inst.symbol} | {strategy.name} | {args.interval} | {len(df)} swiec ==")
        _print_stats("  calosc        ", summarize(trades))
        _print_stats("  in-sample     ", summarize([t for t in trades if t.entry_time < cut]))
        _print_stats("  out-of-sample ", summarize([t for t in trades if t.entry_time >= cut]))


def cmd_walkforward(args) -> None:
    from .validation import verdict, walk_forward

    svc = _service(args)
    for inst in _pick(_instruments(args), args.symbols, args.category):
        try:
            df = svc.get(inst, args.interval)
        except DataSourceError as exc:
            print(f"{inst.symbol}: {exc}")
            continue
        res = walk_forward(df, REGISTRY[args.strategy], PARAM_GRIDS.get(args.strategy, {}), inst.costs, args.train, args.test)
        print(f"\n== {inst.symbol} | {args.strategy} | {args.interval} | okien: {len(res.folds)} ==")
        for f in res.folds:
            print(f"  test od {f['test_start'].date()}: parametry {f['params']}, transakcji {f['test_trades']}, wynik {f['test_total_r']:+.1f}R")
        _print_stats("  poza proba", res.stats)
        if res.folds:
            v, why = verdict(res.stats, res.folds)
            print(f"  OCENA: {v.upper()} ({why})")


def cmd_report(args) -> None:
    from .report import build_rows, write_report

    insts = [i for i in _pick(_instruments(args), args.symbols, args.category) if i.sources]
    rows = build_rows(insts, _service(args), args.interval, args.strategies or STRATS, args.train, args.test,
                      progress=lambda r: print(f"{r['symbol']:<10} {r['strategy']:<18} {r['verdict']:<5} {r['why']}"))
    html_path, json_path = write_report(rows, args.out, f"walidacja_{args.interval}")
    print(f"\nRaport: {html_path}\nDane:   {json_path}")


def cmd_scan(args) -> None:
    svc = _service(args)
    strategies = [REGISTRY[n]() for n in (args.strategies or STRATS)]
    found = 0
    for inst in _pick(_instruments(args), args.symbols, args.category):
        try:
            df = svc.get(inst, args.interval, refresh=not args.offline)
        except DataSourceError:
            continue
        for strategy in strategies:
            sig = latest_signal(inst, strategy, df)
            if sig:
                found += 1
                print(f"{sig.symbol:<10} {sig.direction:<5} {sig.strategy:<18} {sig.time:%Y-%m-%d %H:%M}  "
                      f"cena {sig.ref_price:.5g}  SL {sig.stop_loss:.5g}  TP {sig.take_profit:.5g}  | {sig.rationale}")
    print(f"\nSygnalow: {found}. Ceny pochodza ze zrodla danych, nie z XTB: poziomy przelicz w xStation.")


def cmd_regime(args) -> None:
    from .features import adx, regime

    svc = _service(args)
    for inst in _pick(_instruments(args), args.symbols, args.category):
        try:
            df = svc.get(inst, args.interval).iloc[:-1]
        except DataSourceError:
            continue
        print(f"{inst.symbol:<10} {regime(df).iloc[-1]:<11} ADX {adx(df).iloc[-1]:.0f}")


# ---------- newsy, makro, fundamenty ----------

def cmd_news(args) -> None:
    from .news import fetch_feed, load_feeds

    if args.action == "check-feeds":
        ok = 0
        feeds = load_feeds(_cfg(args, "feeds.yaml"))
        for feed in feeds:
            try:
                items = fetch_feed(feed)
                newest = max((i.published for i in items if i.published), default=None)
                print(f"OK    {feed.name:<34} {len(items):>3} pozycji, najnowsza {newest}")
                ok += bool(items)
            except Exception as exc:
                print(f"BLAD  {feed.name:<34} {type(exc).__name__}: {str(exc)[:90]}")
        print(f"\nDziala: {ok} z {len(feeds)}")
    elif args.action == "poll":
        from .runner import job_news

        ctx = _context(args)
        print(f"Wyslanych alertow: {job_news(ctx)}")
    else:  # list
        rows = _conn(args).execute(
            "SELECT * FROM news WHERE importance >= ? ORDER BY fetched DESC LIMIT ?", (args.min_importance, args.limit)).fetchall()
        for r in rows:
            print(f"[{r['importance']}] {r['published'] or r['fetched']}  {r['symbols']:<28} {r['title'][:90]}")


def cmd_macro(args) -> None:
    from .macro import FairEconomyCalendar, MacroRules, surprise_effects, upcoming, upsert_events
    from .macro.calendar import set_actual

    conn = _conn(args)
    if args.action == "refresh":
        events = FairEconomyCalendar().fetch()
        upsert_events(conn, events)
        print(f"Pobrano wydarzen: {len(events)}, z odczytem 'actual': {sum(e.actual is not None for e in events)}")
    elif args.action == "upcoming":
        rules = MacroRules.from_file(_cfg(args, "macro_rules.yaml"))
        for e in upcoming(conn, timedelta(days=args.days), args.min_importance):
            syms = ",".join(rules.effects_for(e)) or "-"
            print(f"{e.time:%a %d.%m %H:%M} UTC  [{e.importance}] {e.country} {e.name:<40} prognoza {e.forecast}  -> {syms}")
    else:  # set-actual
        ev = set_actual(conn, args.name, args.value)
        if ev is None:
            sys.exit("Nie znaleziono wydarzenia o takiej nazwie")
        rules = MacroRules.from_file(_cfg(args, "macro_rules.yaml"))
        print(f"{ev.country} {ev.name}: odczyt {ev.actual} vs prognoza {ev.forecast} -> {surprise_effects(ev, rules) or 'brak niespodzianki/reguly'}")


def cmd_bias(args) -> None:
    conn = _conn(args)
    if args.action == "update":
        from .runner import job_fundamentals

        ctx = _context(args)
        if ctx.fund_series is None:
            sys.exit("Brak FRED_API_KEY (darmowy klucz: fred.stlouisfed.org)")
        print(f"Zaktualizowano bias dla {job_fundamentals(ctx)} instrumentow")
    elif args.action == "check":
        from .fundamentals import FredClient, load_components

        fred = FredClient()
        ids = sorted({c["series"] for comps in load_components(_cfg(args, "fundamentals.yaml")).values() for c in comps})
        for sid in ids:
            try:
                s = fred.series(sid)
                print(f"OK    {sid:<14} {len(s)} obserwacji, ostatnia {s.index[-1].date()} = {s.iloc[-1]}")
            except Exception as exc:
                print(f"BLAD  {sid:<14} {str(exc)[:100]}")
    for r in conn.execute("SELECT * FROM fundamental_bias ORDER BY bias DESC"):
        print(f"{r['symbol']:<10} bias {r['bias']:+.2f}  ({r['updated'][:16]})")


# ---------- dziennik i praca ciagla ----------

def cmd_journal(args) -> None:
    conn = _conn(args)
    print("Skutecznosc na zywo (forward test):")
    for s in journal.stats(conn):
        exp = f"{s['expectancy_r']:+.2f}R" if s["expectancy_r"] is not None else "–"
        print(f"  {s['strategy']:<18} {s['interval']:<3} sygnalow {s['total']}, rozliczonych {s['resolved']}, "
              f"wygranych {s['wins'] or 0}, oczekiwana {exp}")
    print("\nOstatnie sygnaly:")
    for r in journal.recent(conn, args.limit):
        res = f"{r['r_result']:+.2f}R" if r["r_result"] is not None else ""
        print(f"  {r['time'][:16]} {r['symbol']:<10} {'LONG' if r['side'] > 0 else 'SHORT':<5} {r['strategy']:<18} {r['status']:<7} {res}")


def cmd_health(args) -> None:
    for r in _conn(args).execute("SELECT * FROM source_health ORDER BY fail_streak DESC, source"):
        state = "OK  " if r["fail_streak"] == 0 else f"BLAD x{r['fail_streak']}"
        print(f"{state:<8} {r['source']:<36} ostatnio ok: {r['last_ok'] or '-'}  {(r['last_error'] or '')[:70] if r['fail_streak'] else ''}")


def cmd_run(args) -> None:
    from .runner import run_forever, run_once

    from datetime import datetime, timezone

    from .scanner import due_intervals

    ctx = _context(args)
    if not args.once:
        return run_forever(ctx)
    intervals = None
    if args.intervals == ["auto"]:
        intervals = due_intervals(datetime.now(timezone.utc), ctx.settings["scan"]["intervals"])
        print(f"interwaly w tym przebiegu: {intervals}")
    elif args.intervals:
        intervals = args.intervals
    for name, result in run_once(ctx, args.jobs, intervals).items():
        print(f"{name:<13} {result}")


def cmd_sync(args) -> None:
    from . import sync

    sb, conn = sync.SupabaseClient(), _conn(args)
    if args.action in ("pull", "both"):
        print(f"pull: otwarte sygnaly {sync.pull_open_signals(conn, sb)}, newsy {sync.pull_news_directions(conn, sb)}")
    if args.action in ("push", "both"):
        print(f"push: {sync.push(conn, sb)}")


def cmd_export_config(args) -> None:
    """Zapisuje konfiguracje toru szybkiego jako JSON dla funkcji Supabase (jedno zrodlo prawdy: pliki YAML)."""
    import json

    import yaml

    from .news import load_feeds

    instruments = _instruments(args)
    kw = yaml.safe_load(_cfg(args, "keywords.yaml").read_text(encoding="utf-8"))
    known = set(instruments)
    settings = load_settings(_cfg(args, "settings.yaml"))
    out = {
        "symbols": sorted(known),
        "feeds": [vars(f) for f in load_feeds(_cfg(args, "feeds.yaml"))],
        "keywords": {
            "instruments": {s: w for s, w in kw.get("instruments", {}).items() if s in known and w},
            "topics": {n: {"keywords": t["keywords"], "symbols": [s for s in t["symbols"] if s in known]} for n, t in kw.get("topics", {}).items()},
            "high_impact": kw.get("high_impact", []),
        },
        "macro_rules": yaml.safe_load(_cfg(args, "macro_rules.yaml").read_text(encoding="utf-8"))["rules"],
        "llm": yaml.safe_load(_cfg(args, "llm.yaml").read_text(encoding="utf-8")),
        "news": settings["news"], "macro": settings["macro"], "quiet_hours": settings["quiet_hours"],
    }
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"Zapisano {path} ({len(out['feeds'])} feedow, {len(out['symbols'])} symboli)")


def cmd_dashboard(args) -> None:
    from .dashboard import write

    print(f"Panel: {write(_conn(args), args.out)}")


def cmd_notify_test(args) -> None:
    from .notify import notifier_from_env

    n = notifier_from_env()
    print(f"{type(n).__name__}: {'wyslano' if n.send('Test powiadomien: Analizator CFD dziala.') else 'BLAD'}")


def main(argv: list[str] | None = None) -> None:
    p = argparse.ArgumentParser(prog="cfd", description="Analizator CFD")
    p.add_argument("--config-dir", default="config")
    p.add_argument("--data-dir", default="data")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    def add(name, fn, help_, symbols=True, interval=True):
        sp = sub.add_parser(name, help=help_)
        if symbols:
            sp.add_argument("symbols", nargs="*", help="symbole XTB; puste = wszystkie")
            sp.add_argument("--category")
        if interval:
            sp.add_argument("--interval", default="1d", choices=["30m", "1h", "4h", "1d"])
        sp.set_defaults(fn=fn)
        return sp

    sp = add("instruments", cmd_instruments, "lista instrumentow i mapowan", symbols=False, interval=False)
    sp.add_argument("--category")
    add("check-sources", cmd_check_sources, "sprawdz, ktore mapowania zrodel dzialaja", interval=False)
    add("fetch", cmd_fetch, "pobierz/uzupelnij swiece do cache")

    sp = add("backtest", cmd_backtest, "backtest strategii z kosztami")
    sp.add_argument("--strategy", default="trend_pullback", choices=STRATS)
    sp.add_argument("--split", type=float, default=0.7)
    sp.add_argument("--max-bars", type=int)
    sp.add_argument("--refresh", action="store_true")

    sp = add("walkforward", cmd_walkforward, "walidacja walk-forward jednej strategii")
    sp.add_argument("--strategy", default="trend_pullback", choices=STRATS)
    sp.add_argument("--train", type=int, default=750)
    sp.add_argument("--test", type=int, default=250)

    sp = add("report", cmd_report, "raport walidacji: wszystkie instrumenty x strategie (HTML + JSON)")
    sp.add_argument("--strategies", nargs="*", choices=STRATS)
    sp.add_argument("--train", type=int, default=750)
    sp.add_argument("--test", type=int, default=250)
    sp.add_argument("--out", default="reports")

    sp = add("scan", cmd_scan, "sygnaly z ostatniej zamknietej swiecy")
    sp.add_argument("--strategies", nargs="*", choices=STRATS)
    sp.add_argument("--offline", action="store_true")

    add("regime", cmd_regime, "rezim rynku (trend/konsolidacja) na podstawie cache")

    sp = add("news", cmd_news, "newsy: check-feeds | poll | list", symbols=False, interval=False)
    sp.add_argument("action", choices=["check-feeds", "poll", "list"])
    sp.add_argument("--min-importance", type=int, default=2)
    sp.add_argument("--limit", type=int, default=30)

    sp = add("macro", cmd_macro, "kalendarz makro: refresh | upcoming | set-actual", symbols=False, interval=False)
    sp.add_argument("action", choices=["refresh", "upcoming", "set-actual"])
    sp.add_argument("--days", type=float, default=7)
    sp.add_argument("--min-importance", type=int, default=2)
    sp.add_argument("--name")
    sp.add_argument("--value", type=float)

    sp = add("bias", cmd_bias, "bias fundamentalny: update | show | check", symbols=False, interval=False)
    sp.add_argument("action", choices=["update", "show", "check"])

    sp = add("journal", cmd_journal, "dziennik sygnalow i skutecznosc na zywo", symbols=False, interval=False)
    sp.add_argument("--limit", type=int, default=20)
    add("health", cmd_health, "stan zrodel danych", symbols=False, interval=False)
    sp = add("run", cmd_run, "praca ciagla (albo --once: jeden przebieg)", symbols=False, interval=False)
    sp.add_argument("--once", action="store_true")
    sp.add_argument("--jobs", nargs="*", choices=["fundamentals", "macro", "news", "scan"], help="domyslnie wszystkie")
    sp.add_argument("--intervals", nargs="*", help="np. 1h 4h albo 'auto' = te, na ktorych wlasnie zamknela sie swieca")
    sp = add("sync", cmd_sync, "synchronizacja z Supabase: push | pull | both", symbols=False, interval=False)
    sp.add_argument("action", choices=["push", "pull", "both"])
    sp = add("export-config", cmd_export_config, "konfiguracja dla funkcji Supabase (JSON)", symbols=False, interval=False)
    sp.add_argument("--out", default="supabase/functions/_shared/config.json")
    sp = add("dashboard", cmd_dashboard, "wygeneruj statyczny panel HTML", symbols=False, interval=False)
    sp.add_argument("--out", default="reports/panel.html")
    add("notify-test", cmd_notify_test, "wyslij testowe powiadomienie", symbols=False, interval=False)

    args = p.parse_args(argv)
    load_dotenv()
    logging.basicConfig(level=logging.INFO if args.verbose else logging.ERROR)
    logging.getLogger("yfinance").setLevel(logging.CRITICAL)
    args.fn(args)


if __name__ == "__main__":
    main()
