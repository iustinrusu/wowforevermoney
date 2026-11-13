"""Price history in SQLite: one row per item each time TSM delivers a new realm scan.

TSM's data file only holds averages (14-day, recent, long-term), not a time series, so the app keeps its own.
Every snapshot is kept for FULL_DAYS; older days are folded into one daily candle per item (open, high, low,
close of the lowest listing, plus the day's average listings, realm average, region sale price and sold/day),
kept for KEEP_DAYS. Snapshots only exist for times the app was running.
"""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager

from .paths import DATA

DAY = 86400
FULL_DAYS = 14       # every snapshot (about hourly) for two weeks
KEEP_DAYS = 365      # then one daily candle per item for a year
SERIES_COLS = ('ts', 'min_buyout', 'num_auctions', 'market', 'region_market', 'region_sale', 'sold_per_day')


class History:
    def __init__(self, path=None):
        self.path = path or (DATA / 'history.db')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        with self._conn() as c:
            c.executescript('''
                CREATE TABLE IF NOT EXISTS prices (
                    ts INTEGER NOT NULL, item INTEGER NOT NULL,
                    min_buyout INTEGER, num_auctions INTEGER, market INTEGER,
                    region_market INTEGER, region_sale INTEGER, sold_per_day REAL, sale_rate REAL,
                    PRIMARY KEY (item, ts)) WITHOUT ROWID;
                CREATE INDEX IF NOT EXISTS prices_ts ON prices(ts);
                CREATE TABLE IF NOT EXISTS scans (ts INTEGER PRIMARY KEY, realm TEXT, recorded INTEGER);
                CREATE TABLE IF NOT EXISTS daily (
                    item INTEGER NOT NULL, day INTEGER NOT NULL,
                    open INTEGER, high INTEGER, low INTEGER, close INTEGER, num_auctions REAL, market INTEGER,
                    region_market INTEGER, region_sale INTEGER, sold_per_day REAL, scans INTEGER,
                    PRIMARY KEY (item, day)) WITHOUT ROWID;
            ''')

    @contextmanager
    def _conn(self):
        """A connection that commits on success and is always closed (sqlite3's own context manager doesn't close)."""
        conn = sqlite3.connect(self.path, timeout=10)
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def record(self, realm: str, scan_time: int, prices: dict[int, dict]) -> bool:
        """Store a snapshot once per realm scan time. Returns True if it was new."""
        if not scan_time:
            return False
        with self._lock, self._conn() as c:
            if c.execute('SELECT 1 FROM scans WHERE ts=?', (scan_time,)).fetchone():
                return False
            rows = [(scan_time, iid, p.get('minBuyout'), p.get('numAuctions', 0), p.get('marketValue'),
                     p.get('regionMarketValue'), p.get('regionSale'), p.get('regionSoldPerDay'),
                     p.get('regionSalePercent'))
                    for iid, p in prices.items() if p.get('marketValue') or p.get('minBuyout')]
            c.executemany('INSERT OR REPLACE INTO prices VALUES (?,?,?,?,?,?,?,?,?)', rows)
            c.execute('INSERT INTO scans VALUES (?,?,?)', (scan_time, realm, int(time.time())))
        self.compact()
        return True

    def compact(self, now: float | None = None) -> int:
        """Fold snapshots older than FULL_DAYS into daily candles; drop anything older than KEEP_DAYS.

        Returns the number of days folded. Only whole days (UTC) before the cutoff are folded.
        """
        now = int(now or time.time())
        fold_before = (now - FULL_DAYS * DAY) // DAY * DAY
        with self._lock, self._conn() as c:
            days = [d for (d,) in c.execute('SELECT DISTINCT ts / ? FROM prices WHERE ts < ?', (DAY, fold_before))]
            for day in days:
                lo, hi = day * DAY, (day + 1) * DAY
                agg: dict[int, dict] = {}
                # merge into a candle already folded for this day (its scans came first: scans arrive in order)
                for item, o, h, l, cl, n, mv, rm, rs, spd, k in c.execute(
                        'SELECT item, open, high, low, close, num_auctions, market, region_market, region_sale, '
                        'sold_per_day, scans FROM daily WHERE day=?', (day,)):
                    agg[item] = {'open': o, 'high': h, 'low': l, 'close': cl, 'n': [n or 0] * (k or 1),
                                 'mv': mv, 'rm': rm, 'rs': rs, 'spd': spd, 'scans': k or 1}
                for item, ts, mb, n, mv, rm, rs, spd in c.execute(
                        'SELECT item, ts, min_buyout, num_auctions, market, region_market, region_sale, sold_per_day '
                        'FROM prices WHERE ts >= ? AND ts < ? ORDER BY item, ts', (lo, hi)):
                    a = agg.setdefault(item, {'open': None, 'high': None, 'low': None, 'close': None, 'n': [],
                                              'mv': None, 'rm': None, 'rs': None, 'spd': None, 'scans': 0})
                    a['scans'] += 1
                    a['n'].append(n or 0)
                    if mb and mb > 0:
                        a['open'] = a['open'] if a['open'] is not None else mb
                        a['high'] = mb if a['high'] is None else max(a['high'], mb)
                        a['low'] = mb if a['low'] is None else min(a['low'], mb)
                        a['close'] = mb
                    a['mv'], a['rm'], a['rs'], a['spd'] = mv or a['mv'], rm or a['rm'], rs or a['rs'], spd or a['spd']
                c.executemany('INSERT OR REPLACE INTO daily VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
                              [(item, day, a['open'], a['high'], a['low'], a['close'], sum(a['n']) / len(a['n']),
                                a['mv'], a['rm'], a['rs'], a['spd'], a['scans']) for item, a in agg.items()])
                c.execute('DELETE FROM prices WHERE ts >= ? AND ts < ?', (lo, hi))
            keep_after = now - KEEP_DAYS * DAY
            c.execute('DELETE FROM daily WHERE day < ?', (keep_after // DAY,))
            c.execute('DELETE FROM scans WHERE ts < ?', (keep_after,))
            return len(days)

    def series(self, item: int, days: int = KEEP_DAYS) -> list[dict]:
        """Oldest first: daily candles for folded days (ts = noon UTC, with open/high/low/close), then snapshots."""
        since = int(time.time()) - days * DAY
        with self._conn() as c:
            out = [{'ts': day * DAY + DAY // 2, 'min_buyout': close, 'num_auctions': n, 'market': mv,
                    'region_market': rm, 'region_sale': rs, 'sold_per_day': spd,
                    'open': o, 'high': h, 'low': lo, 'close': close, 'daily': True}
                   for day, o, h, lo, close, n, mv, rm, rs, spd in c.execute(
                       'SELECT day, open, high, low, close, num_auctions, market, region_market, region_sale, '
                       'sold_per_day FROM daily WHERE item=? AND day >= ? ORDER BY day', (item, since // DAY))]
            cur = c.execute(f'SELECT {", ".join(SERIES_COLS)} FROM prices WHERE item=? AND ts>=? ORDER BY ts',
                            (item, since))
            out += [dict(zip(SERIES_COLS, r)) for r in cur.fetchall()]
            return out

    def previous(self, before_ts: int) -> dict[int, dict]:
        """The snapshot just before the given scan time."""
        with self._conn() as c:
            row = c.execute('SELECT MAX(ts) FROM scans WHERE ts < ?', (before_ts,)).fetchone()
            if not row or not row[0]:
                return {}
            cur = c.execute('SELECT item, min_buyout, num_auctions, market FROM prices WHERE ts=?', (row[0],))
            return {r[0]: {'minBuyout': r[1], 'numAuctions': r[2], 'marketValue': r[3]} for r in cur.fetchall()}

    def scans(self, limit: int = 50) -> list[dict]:
        with self._conn() as c:
            cur = c.execute('SELECT ts, realm, recorded FROM scans ORDER BY ts DESC LIMIT ?', (limit,))
            return [dict(zip(('ts', 'realm', 'recorded'), r)) for r in cur.fetchall()]
