"""Price history in SQLite: one row per item each time TSM delivers a new realm scan."""
from __future__ import annotations

import sqlite3
import threading
import time
from contextlib import contextmanager

from .paths import DATA

KEEP_DAYS = 45


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
                CREATE TABLE IF NOT EXISTS scans (ts INTEGER PRIMARY KEY, realm TEXT, recorded INTEGER);
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
            cutoff = int(time.time()) - KEEP_DAYS * 86400
            c.execute('DELETE FROM prices WHERE ts < ?', (cutoff,))
            c.execute('DELETE FROM scans WHERE ts < ?', (cutoff,))
            return True

    def series(self, item: int, days: int = 30) -> list[dict]:
        since = int(time.time()) - days * 86400
        with self._conn() as c:
            cols = ('ts', 'min_buyout', 'num_auctions', 'market', 'region_market', 'region_sale', 'sold_per_day')
            cur = c.execute(f'SELECT {", ".join(cols)} FROM prices WHERE item=? AND ts>=? ORDER BY ts', (item, since))
            return [dict(zip(cols, r)) for r in cur.fetchall()]

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
