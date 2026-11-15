"""Change detection between engine runs, and Windows desktop notifications."""
from __future__ import annotations

import json
import subprocess
import time
from collections import deque

from .pricing import fmt_money
from .paths import DATA


UNDERVALUED_TEXT = {
    'contents_unknown': "can be opened but its Forever contents are unknown, so it's valued as a floor. Open one with "
                        'ForeverMoneyBridge enabled (or read its Wowhead Forever page) to value it properly.',
    'no_value': 'no AH price, vendor price, recipe or contents known: worth 0 to the app for now.',
}


def diff_runs(prev: dict | None, cur: dict, settings: dict, names) -> list[dict]:
    """Compare two engine results and return change events worth telling the user about."""
    events = []
    now = int(time.time())
    min_daily = float((settings.get('alerts') or {}).get('min_daily_profit_gold', 5)) * 10000
    cur_by = {o.key: o for o in cur['opportunities']}
    prev_by = {o.key: o for o in prev['opportunities']} if prev else {}
    if prev:
        prev_now = set(prev['top'].get('now', []))
        for key in cur['top'].get('now', []):
            if key not in prev_now:
                o = cur_by[key]
                events.append({'ts': now, 'type': 'new_top', 'key': key, 'item_id': o.item_id,
                               'text': f'New top pick: {o.title} (~{fmt_money(o.daily)}/day)',
                               'important': o.daily >= min_daily})
        # a newly looted/caught item the app can't value properly: say so instead of silently undervaluing it
        before = {(u['item_id'], u['issue']) for u in prev.get('undervalued', [])}
        for u in cur.get('undervalued', []):
            if u['issue'] in UNDERVALUED_TEXT and (u['item_id'], u['issue']) not in before:
                events.append({'ts': now, 'type': 'undervalued', 'key': f"value:{u['item_id']}", 'item_id': u['item_id'],
                               'text': f"{u['name']}: {UNDERVALUED_TEXT[u['issue']]}", 'important': False})
    watch = {int(x) for x in settings.get('watchlist') or []}
    for iid in watch:
        old, new = (prev or {}).get('prices', {}).get(iid), cur.get('prices', {}).get(iid)
        if old and new and old.get('minBuyout') and new.get('minBuyout'):
            change = new['minBuyout'] / old['minBuyout'] - 1
            if abs(change) >= 0.2:
                events.append({'ts': now, 'type': 'watch', 'item_id': iid, 'key': f'watch:{iid}',
                               'text': f'{names(iid)} {"up" if change > 0 else "down"} {abs(change):.0%} '
                                       f'to {fmt_money(new["minBuyout"])}', 'important': True})
    return events


class EventLog:
    def __init__(self, size=300):
        self.events = deque(maxlen=size)
        self.path = DATA / 'events.jsonl'
        if self.path.exists():
            for line in self.path.read_text(encoding='utf-8').splitlines()[-size:]:
                try:
                    self.events.append(json.loads(line))
                except ValueError:
                    pass

    def add(self, events: list[dict]):
        if not events:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.path, 'a', encoding='utf-8') as fh:
            for e in events:
                self.events.append(e)
                fh.write(json.dumps(e) + '\n')

    def recent(self, n=100) -> list[dict]:
        return list(self.events)[-n:][::-1]


_TOAST = r'''
$ErrorActionPreference = 'Stop'
[Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
[Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
$xml = New-Object Windows.Data.Xml.Dom.XmlDocument
$xml.LoadXml("<toast><visual><binding template='ToastGeneric'><text>$env:WFM_TITLE</text><text>$env:WFM_BODY</text></binding></visual></toast>")
$appId = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($appId).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
'''


def _xml_escape(s: str) -> str:
    return s.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;').replace('"', '&quot;').replace("'", '&apos;')


def desktop_notify(title: str, body: str):
    """Show a Windows toast. Text goes through environment variables, never into the script itself."""
    try:
        import os
        env = dict(os.environ, WFM_TITLE=_xml_escape(title)[:120], WFM_BODY=_xml_escape(body)[:400])
        subprocess.Popen(['powershell', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass', '-Command', _TOAST],
                         env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                         creationflags=getattr(subprocess, 'CREATE_NO_WINDOW', 0))
    except OSError:
        pass
