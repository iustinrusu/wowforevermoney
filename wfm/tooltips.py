"""Fill in items the client's ItemSparse table doesn't ship (about 13k of 32k items in Forever).

Uses Wowhead's public tooltip API (the one their embeddable item tooltips use), slowly, once per item,
cached forever in data/tooltips.json. Only items that matter (have TSM prices, or are in your bags)
are fetched.
"""
from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.request

from .paths import DATA

URL = 'https://nether.wowhead.com/forever/tooltip/item/{}?locale=0'
USER_AGENT = 'WoWForeverMoney/0.1 (personal gold tool)'
DELAY_SECONDS = 1.5
_MONEY = {'moneygold': 10000, 'moneysilver': 100, 'moneycopper': 1}


def parse_tooltip(data: dict) -> dict:
    html = data.get('tooltip') or ''
    info = {'name': data.get('name') or '', 'quality': int(data.get('quality') or 1), 'icon': data.get('icon')}
    m = re.search(r'whtt-sellprice">Sell Price:(.*?)</div>', html)
    sell = 0
    if m:
        for cls, amount in re.findall(r'class="(money\w+)">(\d+)<', m.group(1)):
            sell += _MONEY.get(cls, 0) * int(amount)
    info['sell_price'] = sell
    info['openable'] = 'Right Click to Open' in html
    m = re.search(r'Requires Level (?:<!--rlvl-->)?(\d+)', html)
    info['req_level'] = int(m.group(1)) if m else 0
    m = re.search(r'Item Level (?:<!--ilvl-->)?(\d+)', html)
    info['item_level'] = int(m.group(1)) if m else 0
    info['bonding'] = 1 if 'Binds when picked up' in html else (2 if 'Binds when equipped' in html else 0)
    info['fetched'] = int(time.time())
    return info


class TooltipCache:
    def __init__(self, log=print):
        self.path = DATA / 'tooltips.json'
        self.log = log
        self.lock = threading.Lock()
        self.data: dict[str, dict] = {}
        if self.path.exists():
            try:
                self.data = json.loads(self.path.read_text(encoding='utf-8'))
            except ValueError:
                self.data = {}
        self.queue: list[int] = []
        self.failed: dict[int, int] = {}
        self._thread = None
        self.on_batch = None   # callback when a batch of new items arrives

    def get(self, iid: int) -> dict | None:
        return self.data.get(str(iid))

    def want(self, ids):
        with self.lock:
            have = set(self.data)
            queued = set(self.queue)
            for i in ids:
                if str(i) not in have and i not in queued and self.failed.get(i, 0) < 3:
                    self.queue.append(i)
        if self.queue and (not self._thread or not self._thread.is_alive()):
            self._thread = threading.Thread(target=self._run, daemon=True, name='tooltips')
            self._thread.start()

    def pending(self) -> int:
        return len(self.queue)

    def _save(self):
        tmp = self.path.with_suffix('.part')
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(self.data), encoding='utf-8')
        tmp.replace(self.path)

    def _run(self):
        self.log(f'Fetching item info for {len(self.queue)} items from Wowhead tooltips (slowly, cached)')
        new = 0
        while True:
            with self.lock:
                if not self.queue:
                    break
                iid = self.queue.pop(0)
            try:
                req = urllib.request.Request(URL.format(iid), headers={'User-Agent': USER_AGENT})
                with urllib.request.urlopen(req, timeout=20) as resp:
                    info = parse_tooltip(json.loads(resp.read()))
                with self.lock:
                    self.data[str(iid)] = info
                new += 1
            except (urllib.error.URLError, ValueError, OSError) as e:
                self.failed[iid] = self.failed.get(iid, 0) + 1
                if isinstance(e, urllib.error.HTTPError) and e.code in (403, 429):
                    self.log(f'Wowhead tooltips answered {e.code}; pausing tooltip fetching for 10 minutes')
                    time.sleep(600)
            if new and new % 20 == 0:
                with self.lock:
                    self._save()
                if self.on_batch:
                    self.on_batch()
            time.sleep(DELAY_SECONDS)
        with self.lock:
            self._save()
        if new and self.on_batch:
            self.on_batch()
        self.log(f'Item info fetch done: {new} new items')
