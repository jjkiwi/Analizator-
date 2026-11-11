from __future__ import annotations

import os
from pathlib import Path

import yaml

DEFAULTS = {
    "scan": {"every_minutes": 15, "intervals": ["1d"], "strategies": ["trend_pullback"], "alert_strategies": [], "expire_bars": 40},
    "news": {"every_seconds": 60, "alert_min_importance": 3, "max_age_hours": 12, "use_llm": True},
    "macro": {"refresh_minutes": 60, "alert_minutes_before": 30, "alert_min_importance": 3},
    "fundamentals": {"refresh_hours": 24},
    "health": {"alert_after_failures": 3},
    "dashboard": {"refresh_minutes": 5, "path": "reports/panel.html"},
    "quiet_hours": {"start": 23, "end": 8, "tz": "Europe/Warsaw"},
}


def load_settings(path: Path | str = "config/settings.yaml") -> dict:
    out = {k: dict(v) for k, v in DEFAULTS.items()}
    p = Path(path)
    if p.exists():
        for section, values in (yaml.safe_load(p.read_text(encoding="utf-8")) or {}).items():
            out.setdefault(section, {}).update(values or {})
    return out


def load_dotenv(path: Path | str = ".env") -> None:
    """Minimalny odpowiednik python-dotenv: KLUCZ=wartosc, bez nadpisywania istniejacych zmiennych."""
    p = Path(path)
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            if value.strip():
                os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
