"""Done for today: suggestions you have acted on (the user's idea, 2026-11-15).

Once you have listed the day's share of a craft (or done a plan step), that suggestion is stale until tomorrow: it
leaves the plan and Top picks and the next best takes its place. A partial tick ("listed 2 of the 5") leaves the row
with what's left for today. Kept per character in data/done.json; a new day starts at DAY_STARTS (hour, local time),
about when the realm's daily reset happens.
"""
from __future__ import annotations

import json
import threading
import time
from pathlib import Path

from .paths import DATA

PATH = DATA / 'done.json'
DAY_STARTS = 4
_lock = threading.Lock()


def day_key(now: float | None = None, starts: int = DAY_STARTS) -> str:
    return time.strftime('%Y-%m-%d', time.localtime((now or time.time()) - starts * 3600))


def _load(path: Path) -> dict:
    try:
        d = json.loads(path.read_text(encoding='utf-8'))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def today(character: str, path: Path | None = None, now: float | None = None) -> dict[str, dict]:
    """key -> {done, of, at, title} for this character today (yesterday's ticks are gone)."""
    c = _load(path or PATH).get(character or '') or {}
    return c.get('items') or {} if c.get('day') == day_key(now) else {}


def mark(character: str, key: str, done: float, of: float, title: str = '', undo: bool = False,
         path: Path | None = None, now: float | None = None) -> dict[str, dict]:
    """Tick (or untick) a suggestion for today. done = how many you listed or did, of = how many were suggested."""
    path = path or PATH
    with _lock:
        d = _load(path)
        c = d.get(character or '') or {}
        if c.get('day') != day_key(now):
            c = {'day': day_key(now), 'items': {}}
        if undo:
            c['items'].pop(key, None)
        else:
            c['items'][key] = {'done': max(0.0, float(done)), 'of': max(0.0, float(of)), 'title': title[:120],
                               'at': int(now or time.time())}
        d[character or ''] = c
        path.write_text(json.dumps(d, indent=1), encoding='utf-8')
        return c['items']


def full(entry: dict) -> bool:
    return entry['done'] >= entry['of']
