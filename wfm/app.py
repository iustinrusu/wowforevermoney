"""The running app: watches every data source, recomputes, keeps history, and serves the web page."""
from __future__ import annotations

import json
import queue
import threading
import time
import traceback
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from . import audit
from . import profile as profile_mod
from .alerts import EventLog, desktop_notify, diff_runs
from .engine import Engine
from .history import History
from .paths import DATA, ROOT, WEB, GamePaths, find_wow_dir
from .pricing import ah_sell, fmt_money, proceeds
from .settings import Settings
from .world import World

POLL_SECONDS = 15
WOWHEAD = 'https://www.wowhead.com/forever/item={}'


def log(msg: str):
    line = f'[{time.strftime("%H:%M:%S")}] {msg}'
    print(line, flush=True)
    try:
        DATA.mkdir(parents=True, exist_ok=True)
        with open(DATA / 'app.log', 'a', encoding='utf-8') as fh:
            fh.write(line + '\n')
    except OSError:
        pass


class App:
    def __init__(self):
        self.settings = Settings()
        wow = find_wow_dir(self.settings.snapshot().get('wow_dir'))
        if not wow:
            raise SystemExit('Could not find your World of Warcraft folder with _forever_ in it. '
                             'Set "wow_dir" in data/settings.json.')
        self.world = World(GamePaths(wow), self.settings, log)
        self.history = History()
        self.events = EventLog()
        self.result: dict | None = None
        self.generated_at = 0
        self.audit: list[dict] = []
        self.listeners: list[queue.Queue] = []
        self.lock = threading.RLock()
        self._settings_dirty = threading.Event()
        self._force = threading.Event()
        self.tips = self._load_tips()

    # ---------- compute ----------
    def _load_tips(self) -> dict:
        p = DATA / 'tips.json'
        try:
            return json.loads(p.read_text(encoding='utf-8')) if p.exists() else {}
        except ValueError:
            return {}

    def effective_settings(self) -> tuple[dict, dict]:
        """Manual settings with detected character data (level, gold, faction, professions) applied on top."""
        return profile_mod.apply(self.settings.snapshot(), self.world.profile)

    def recompute(self, reason: str):
        with self.lock:
            t = time.time()
            settings, _ = self.effective_settings()
            result = Engine(self.world, settings).run()
            result['prices'] = self.world.prices
            result['by_key'] = {o.key: o for o in result['opportunities']}
            # Only market/data changes produce "what changed" events; changing your settings shouldn't spam alerts.
            events = diff_runs(self.result, result, settings, self.name) if reason.startswith('data changed') else []
            self.result, self.generated_at = result, int(time.time())
            self.audit = audit.run(self.world, Engine(self.world, settings))
            self.tips = self._load_tips()
        log(f'Recomputed ({reason}) in {time.time() - t:.1f}s: {len(result["opportunities"])} opportunities')
        if events:
            self.events.add(events)
            alerts = settings.get('alerts') or {}
            important = [e for e in events if e.get('important')]
            if alerts.get('enabled') and alerts.get('desktop') and important:
                body = '\n'.join(e['text'] for e in important[:3])
                desktop_notify(f'WoW Forever Money: {len(important)} new', body)
        self.broadcast('update', {'version': self.world.version, 'generated_at': self.generated_at,
                                  'events': events[:10]})

    def record_history(self):
        pd = self.world.price_data
        if not pd:
            return
        realm = self.settings.snapshot().get('realm')
        times = [d.download_time for d in pd.datasets if d.scope == realm and d.kind == 'AUCTIONDB_NON_COMMODITY_DATA']
        if times and self.history.record(realm, max(times), self.world.prices):
            log(f'Saved price history for scan at {time.strftime("%Y-%m-%d %H:%M", time.localtime(max(times)))}')

    def watch_loop(self):
        while True:
            try:
                if self._force.is_set():
                    self._force.clear()
                    self._settings_dirty.clear()
                    log('Manual refresh: re-reading every source')
                    self.world.wago_checked = 0
                    self.world.load_all()
                    self.record_history()
                    self.recompute('data changed: manual refresh')
                    self._settings_dirty.wait(POLL_SECONDS)
                    continue
                changed = self.world.poll()
                if changed:
                    log(f'Reloaded: {", ".join(changed)}')
                    if 'tsm' in changed:
                        self.record_history()
                    self.recompute('data changed: ' + ', '.join(changed))
                elif self._settings_dirty.is_set():
                    self._settings_dirty.clear()
                    self.recompute('settings changed')
                else:
                    self.broadcast('tick', {'freshness': self.world.freshness()})
            except Exception:
                log('Watcher error:\n' + traceback.format_exc())
            self._settings_dirty.wait(POLL_SECONDS)

    def start(self):
        try:
            profile_mod.install_addon(ROOT / 'addon' / profile_mod.ADDON_NAME, self.world.paths.addons, log)
        except OSError as e:
            log(f'Could not install the ForeverMoneyBridge addon: {e}')
        log('Loading data...')
        self.world.load_all()
        self.record_history()
        self.recompute('startup')
        threading.Thread(target=self.watch_loop, daemon=True, name='watcher').start()

    # ---------- views ----------
    def name(self, iid: int) -> str:
        it = self.world.gamedata.items.get(iid) if self.world.gamedata else None
        return it.name if it else f'Item {iid}'

    def opp_view(self, o) -> dict:
        d = o.to_dict()
        it = self.world.gamedata.items.get(o.item_id)
        d['name'] = it.name if it else ''
        d['quality'] = it.quality if it else 1
        d['wowhead'] = WOWHEAD.format(o.item_id)
        d['tip'] = (self.tips.get(str(o.item_id)) or {}).get('summary')
        return d

    def state(self) -> dict:
        r = self.result or {'top': {}, 'opportunities': []}
        by = r.get('by_key', {})
        counts = {}
        for o in r['opportunities']:
            counts[o.kind] = counts.get(o.kind, 0) + 1
        pd = self.world.price_data
        effective, detected = self.effective_settings()
        chars = {n: {k: c.get(k) for k in ('name', 'faction', 'level', 'money', 'professions', 'source')}
                 for n, c in (self.world.profile.get('characters') or {}).items()}
        return {
            'generated_at': self.generated_at, 'version': self.world.version,
            'freshness': self.world.freshness(), 'settings': self.settings.snapshot(),
            'effective': effective, 'detected': detected, 'characters': chars,
            'active_character': self.world.profile.get('active'),
            'realms': pd.realms() if pd else [], 'client_build': self.world.client_build,
            'counts': counts, 'audit_summary': audit.summary(self.audit),
            'top': {sec: [self.opp_view(by[k]) for k in keys if k in by] for sec, keys in r['top'].items()},
            'events': self.events.recent(20),
            'professions_available': sorted({rc.profession for rc in self.world.gamedata.recipes}) if self.world.gamedata else [],
        }

    def opps(self, qs: dict) -> list[dict]:
        r = self.result or {'opportunities': []}
        kinds = set(filter(None, (qs.get('kind', [''])[0]).split(',')))
        text = qs.get('q', [''])[0].lower()
        prof = qs.get('profession', [''])[0]
        doable = qs.get('doable', [''])[0] == '1'
        hide_flags = set(filter(None, qs.get('hide', [''])[0].split(',')))
        out = []
        for o in r['opportunities']:
            if kinds and o.kind not in kinds:
                continue
            if prof and o.profession != prof:
                continue
            if doable and not o.doable:
                continue
            if hide_flags and hide_flags & set(o.flags):
                continue
            if text and text not in o.title.lower():
                continue
            out.append(o)
        sort = qs.get('sort', ['daily'])[0]
        out.sort(key=lambda o: (getattr(o, sort, 0) or 0), reverse=True)
        limit = int(qs.get('limit', ['400'])[0])
        return [self.opp_view(o) for o in out[:limit]]

    def search(self, text: str, limit=60) -> list[dict]:
        text = text.lower().strip()
        gd = self.world.gamedata
        if not text or not gd:
            return []
        hits = []
        for it in gd.items.values():
            if text in it.name.lower() or text == str(it.id):
                p = self.world.prices.get(it.id) or {}
                hits.append({'id': it.id, 'name': it.name, 'quality': it.quality, 'category': it.category,
                             'min_buyout': p.get('minBuyout'), 'market': p.get('marketValue'),
                             'listings': p.get('numAuctions', 0), 'sold_per_day': p.get('regionSoldPerDay'),
                             'vendor_sell': it.sell_price, 'has_price': bool(p)})
        hits.sort(key=lambda h: (not h['has_price'], -(h['sold_per_day'] or 0), h['name']))
        return hits[:limit]

    def item(self, iid: int) -> dict:
        w = self.world
        gd = w.gamedata
        it = gd.items.get(iid)
        eng = Engine(w, self.effective_settings()[0])
        qi = (w.questie.items.get(iid) if w.questie else None) or {}
        drops = []
        rates = w.drop_rates.get(iid, {})
        for npc_id in (qi.get('npcDrops') or [])[:40]:
            npc = w.questie.npcs.get(npc_id, {})
            drops.append({'npc': npc_id, 'name': npc.get('name', f'NPC {npc_id}'), 'zone': gd.zones.get(npc.get('zoneID'), ''),
                          'level': f"{npc.get('minLevel', '?')}-{npc.get('maxLevel', '?')}", 'rate': rates.get(npc_id)})
        drops.sort(key=lambda d: -(d['rate'] or 0))
        objects = []
        for oid in (qi.get('objectDrops') or [])[:20]:
            ob = w.questie.objects.get(oid, {})
            objects.append({'id': oid, 'name': ob.get('name', f'Object {oid}'), 'zone': gd.zones.get(ob.get('zoneID'), '')})
        made_by = [{'spell': r.spell_id, 'name': r.name, 'profession': r.profession, 'count': r.product_count,
                    'mats': [{'item_id': m, 'name': self.name(m), 'count': c} for m, c in r.reagents],
                    'thresholds': w.skillup.thresholds.get(r.spell_id)}
                   for r in gd.recipes if r.product_id == iid]
        used_in = [{'spell': r.spell_id, 'name': r.name, 'profession': r.profession, 'product_id': r.product_id,
                    'product': self.name(r.product_id), 'count': c}
                   for r in gd.recipes for m, c in r.reagents if m == iid][:60]
        r = self.result or {'opportunities': [], 'best_use': {}}
        fished_in = []
        for o in r['opportunities']:
            if o.kind != 'fishing_spot':
                continue
            f = next((x for x in o.detail.get('fish', []) if x['item_id'] == iid), None)
            if f and f['share'] > 0:
                fished_in.append({'key': o.key, 'title': o.title, 'share': f['share'], 'classic_share': f['classic_share'],
                                  'observed_share': f['observed_share'], 'count': f['count'],
                                  'zone_skill': o.detail.get('zone_skill'), 'flags': o.flags, 'pools': f['pools']})
        fished_in.sort(key=lambda x: ('classic_unconfirmed' in x['flags'], -x['share']))     # Forever data first
        q = ah_sell(w.prices.get(iid))
        return {
            'id': iid, 'name': it.name if it else self.name(iid), 'quality': it.quality if it else 1,
            'category': it.category if it else '', 'item_level': it.item_level if it else None,
            'req_level': it.req_level if it else None, 'vendor_sell': it.sell_price if it else 0,
            'bonding': it.bonding if it else 0, 'wowhead': WOWHEAD.format(iid),
            'prices': w.prices.get(iid) or {}, 'ah_sell': q.value if q else None, 'ah_sell_source': q.source if q else None,
            'ah_sell_flags': list(q.flags) if q else [],
            'history': self.history.series(iid), 'vendors': eng.vendors_for(iid),
            'vendor_price': (eng.vendor_price(iid) or (None,))[0], 'drops': drops, 'objects': objects,
            'fished_in': fished_in[:25],
            'made_by': made_by, 'used_in': used_in, 'best_use': r.get('best_use', {}).get(iid),
            'opportunities': [self.opp_view(o) for o in r['opportunities'] if o.item_id == iid],
            'tip': self.tips.get(str(iid)),
        }

    def inventory(self) -> list[dict]:
        w = self.world
        r = self.result or {'best_use': {}}
        eng = Engine(w, self.effective_settings()[0])
        valuer = eng.valuer(r.get('best_use') or {})
        out = []
        for char, counts in w.inventory.items():
            rows, total = [], 0
            for iid, n in counts.items():
                it = w.gamedata.items.get(iid)
                if not it:
                    continue
                v = valuer.value(iid)
                _, _, q = eng.sell_value(iid)
                action = v.how[:1].upper() + v.how[1:]
                if v.channel == 'open' and v.contents:
                    action += ': ' + ', '.join(c['name'] for c in v.contents[:3])
                total += v.value * n
                rows.append({'item_id': iid, 'name': it.name, 'quality': it.quality, 'count': n, 'action': action,
                             'unit_value': v.value, 'total': v.value * n,
                             'flags': list(q.flags if q and v.channel == 'AH' else ()) + list(v.flags)})
            rows.sort(key=lambda x: -x['total'])
            out.append({'character': char, 'total': total, 'items': rows})
        return out

    def tsm_export(self, keys: list[str]) -> str:
        by = (self.result or {}).get('by_key', {})
        ids = []
        for k in keys:
            o = by.get(k)
            if not o:
                continue
            if o.kind == 'craft':
                ids.extend(m['item_id'] for m in o.detail.get('mats', []) if m['source'] != 'vendor')
            ids.append(o.item_id)
        seen, out = set(), []
        for i in ids:
            if i and i not in seen:
                seen.add(i)
                out.append(f'i:{i}')
        return ','.join(out)

    # ---------- push ----------
    def broadcast(self, event: str, data: dict):
        msg = f'event: {event}\ndata: {json.dumps(data, default=str)}\n\n'
        for q in list(self.listeners):
            try:
                q.put_nowait(msg)
            except queue.Full:
                pass

    def update_settings(self, changes: dict) -> dict:
        allowed = {'auto_detect', 'character', 'gold_scope', 'realm', 'faction', 'gold', 'level', 'professions', 'preferred', 'switch_bonus', 'ah_cut',
                   'market_share', 'min_sold_per_day', 'show_other_professions', 'include_unverified_recipes',
                   'farm_rates', 'watchlist', 'alerts', 'stale_hours', 'casts_per_hour',
                   'own_logs_for_rates', 'fishing_pools'}
        clean = {k: v for k, v in changes.items() if k in allowed}
        new = self.settings.update(clean)
        if 'realm' in clean:
            with self.world.lock:
                self.world._load_tsm()
                self.world.refresh_freshness()
        self._settings_dirty.set()
        return new


def make_handler(app: App):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'WoWForeverMoney/0.1'

        def log_message(self, fmt, *args):
            pass

        def _json(self, obj, status=200):
            body = json.dumps(obj, default=str).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(body)

        def _static(self, rel: str):
            path = (WEB / rel).resolve()
            if WEB.resolve() not in path.parents and path != WEB.resolve() or not path.is_file():
                self.send_error(404)
                return
            ctype = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css',
                     '.svg': 'image/svg+xml', '.png': 'image/png'}.get(path.suffix, 'application/octet-stream')
            body = path.read_bytes()
            self.send_response(200)
            self.send_header('Content-Type', ctype + ('; charset=utf-8' if ctype.startswith('text') else ''))
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            url = urlparse(self.path)
            qs = parse_qs(url.query)
            try:
                if url.path in ('/', '/index.html'):
                    return self._static('index.html')
                if url.path.startswith('/static/'):
                    return self._static(url.path[len('/static/'):])
                if url.path == '/api/state':
                    return self._json(app.state())
                if url.path == '/api/opps':
                    return self._json(app.opps(qs))
                if url.path == '/api/search':
                    return self._json(app.search(qs.get('q', [''])[0]))
                if url.path == '/api/item':
                    return self._json(app.item(int(qs.get('id', ['0'])[0])))
                if url.path == '/api/inventory':
                    return self._json(app.inventory())
                if url.path == '/api/events':
                    return self._json(app.events.recent(200))
                if url.path == '/api/audit':
                    return self._json(app.audit)
                if url.path == '/api/scans':
                    return self._json(app.history.scans())
                if url.path == '/api/export':
                    keys = [k for k in qs.get('keys', [''])[0].split('|') if k]
                    return self._json({'tsm': app.tsm_export(keys)})
                if url.path == '/api/stream':
                    return self._stream()
                if url.path == '/api/characters':
                    return self._json(app.world.profile)
                self.send_error(404)
            except (BrokenPipeError, ConnectionResetError):
                pass
            except Exception as e:
                log('Request error:\n' + traceback.format_exc())
                self._json({'error': str(e)}, 500)

        def _trusted(self) -> bool:
            """Only this page may change settings: reject other websites (Origin) and DNS-rebinding (Host)."""
            host = (self.headers.get('Host') or '').split(':')[0]
            origin = self.headers.get('Origin')
            ctype = self.headers.get('Content-Type') or ''
            if host not in ('127.0.0.1', 'localhost'):
                return False
            if origin and urlparse(origin).hostname not in ('127.0.0.1', 'localhost'):
                return False
            return ctype.startswith('application/json')

        def do_POST(self):
            url = urlparse(self.path)
            if not self._trusted():
                return self._json({'error': 'forbidden'}, 403)
            length = int(self.headers.get('Content-Length') or 0)
            try:
                body = json.loads(self.rfile.read(length) or b'{}')
                if url.path == '/api/settings':
                    return self._json(app.update_settings(body))
                if url.path == '/api/refresh':
                    app._force.set()
                    app._settings_dirty.set()   # wakes the watcher immediately
                    return self._json({'ok': True})
                self.send_error(404)
            except Exception as e:
                log('Request error:\n' + traceback.format_exc())
                self._json({'error': str(e)}, 500)

        def _stream(self):
            self.send_response(200)
            self.send_header('Content-Type', 'text/event-stream')
            self.send_header('Cache-Control', 'no-cache')
            self.end_headers()
            q: queue.Queue = queue.Queue(maxsize=50)
            app.listeners.append(q)
            try:
                self.wfile.write(b'event: hello\ndata: {}\n\n')
                self.wfile.flush()
                while True:
                    try:
                        msg = q.get(timeout=25)
                    except queue.Empty:
                        msg = ': keepalive\n\n'
                    self.wfile.write(msg.encode('utf-8'))
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            finally:
                if q in app.listeners:
                    app.listeners.remove(q)

    return Handler


_INSTANCE_LOCK_PORT = 47651
_instance_socket = None


def _single_instance() -> bool:
    """Hold a local socket as a mutex so two copies never run (two copies would each poll and fetch)."""
    global _instance_socket
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(('127.0.0.1', _INSTANCE_LOCK_PORT))
    except OSError:
        s.close()
        return False
    _instance_socket = s
    return True


def main(port: int = 8765, open_browser: bool = True):
    if not _single_instance():
        log('WoW Forever Money is already running; open the existing page instead (default http://127.0.0.1:8765/).')
        if open_browser:
            webbrowser.open(f'http://127.0.0.1:{port}/')
        return
    app = App()
    app.start()
    server = ThreadingHTTPServer(('127.0.0.1', port), make_handler(app))
    server.daemon_threads = True
    url = f'http://127.0.0.1:{port}/'
    log(f'WoW Forever Money is running at {url}  (Ctrl+C to stop)')
    if open_browser:
        threading.Timer(1.0, lambda: webbrowser.open(url)).start()
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log('Stopped.')
