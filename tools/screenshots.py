"""Screenshots of every tab, wide and on a phone, for UI reviews (the UI overhaul's before and after pictures).

    python tools/screenshots.py before                    # data/screenshots/before/<tab>-wide.png and <tab>-phone.png
    python tools/screenshots.py after --reduced-motion    # as a visitor who asked their system for less motion
    python tools/screenshots.py check --no-shots          # only the checks below, no pictures

The app must be running (python run.py --no-browser --port 8765). This drives Microsoft Edge (or Chrome) without a
window through its DevTools protocol, standard library only, in a throw-away browser profile (your own browser and
its saved tab are not touched). For every tab it also reports what the UI rules need checking:
  - sideways scrolling at each width (the page wider than the window), with the widest elements to blame,
  - console errors and warnings, and script errors on the page.
The pictures show your characters and gold, so they stay in data/ (never committed).
"""
import argparse
import base64
import json
import os
import shutil
import socket
import struct
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
BROWSERS = [
    r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',
    r'C:\Program Files\Google\Chrome\Application\chrome.exe',
]
SIZES = {'wide': (1440, 900, False), 'phone': (375, 812, True)}
# errors from other sites, not the app: Wowhead's tooltip script often can't reach its server from a throw-away
# headless profile (net::ERR_CERT_VERIFIER_CHANGED), and web fonts may fail the same way
OUTSIDE = ('wowhead.com', 'zamimg.com', 'Wowhead tooltips', 'fonts.googleapis.com', 'fonts.gstatic.com')


class WebSocket:
    """Just enough of a WebSocket client (RFC 6455) for the DevTools protocol: text messages, ping, close."""

    def __init__(self, url: str):
        u = urlparse(url)
        self.sock = socket.create_connection((u.hostname, u.port), timeout=120)
        key = base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.hostname}:{u.port}\r\nUpgrade: websocket\r\n'
                           f'Connection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        self.buf = bytearray()
        while b'\r\n\r\n' not in self.buf:
            self._fill()
        end = self.buf.index(b'\r\n\r\n')
        head = bytes(self.buf[:end])
        del self.buf[:end + 4]
        if b' 101 ' not in head.split(b'\r\n')[0]:
            raise RuntimeError('WebSocket handshake failed: ' + head.decode(errors='replace'))

    def _fill(self):
        chunk = self.sock.recv(1 << 20)
        if not chunk:
            raise ConnectionError('browser closed the connection')
        self.buf += chunk

    def _take(self, n: int) -> bytes:
        while len(self.buf) < n:
            self._fill()
        out = bytes(self.buf[:n])
        del self.buf[:n]
        return out

    def _frame(self, opcode: int, payload: bytes):
        head = bytearray([0x80 | opcode])
        n = len(payload)
        if n < 126:
            head.append(0x80 | n)
        elif n < 1 << 16:
            head.append(0x80 | 126); head += struct.pack('>H', n)
        else:
            head.append(0x80 | 127); head += struct.pack('>Q', n)
        mask = os.urandom(4)
        head += mask
        self.sock.sendall(bytes(head) + bytes(b ^ mask[i % 4] for i, b in enumerate(payload)))

    def send(self, text: str):
        self._frame(0x1, text.encode())

    def recv(self) -> str:
        parts = []
        while True:
            b0, b1 = self._take(2)
            opcode, n = b0 & 0x0F, b1 & 0x7F
            if n == 126:
                n = struct.unpack('>H', self._take(2))[0]
            elif n == 127:
                n = struct.unpack('>Q', self._take(8))[0]
            mask = self._take(4) if b1 & 0x80 else None
            data = self._take(n)
            if mask:
                data = bytes(b ^ mask[i % 4] for i, b in enumerate(data))
            if opcode == 0x9:
                self._frame(0xA, data)
                continue
            if opcode == 0x8:
                raise ConnectionError('browser closed the connection')
            if opcode in (0x0, 0x1, 0x2):
                parts.append(data)
                if b0 & 0x80:
                    return b''.join(parts).decode()


class Page:
    """One browser tab over the DevTools protocol; collects console errors as they come."""

    def __init__(self, ws_url: str):
        self.ws = WebSocket(ws_url)
        self.next_id = 0
        self.problems: list[str] = []

    def call(self, method: str, **params):
        self.next_id += 1
        my_id = self.next_id
        self.ws.send(json.dumps({'id': my_id, 'method': method, 'params': params}))
        while True:
            msg = json.loads(self.ws.recv())
            if msg.get('id') == my_id:
                if 'error' in msg:
                    raise RuntimeError(f"{method}: {msg['error']}")
                return msg.get('result', {})
            self._event(msg)

    def _event(self, msg: dict):
        m, p = msg.get('method'), msg.get('params', {})
        if m == 'Runtime.consoleAPICalled' and p.get('type') in ('error', 'warning', 'assert'):
            text = ' '.join(str(a.get('value', a.get('description', ''))) for a in p.get('args', []))
            self.problems.append(f"console {p['type']}: {text[:300]}")
        elif m == 'Runtime.exceptionThrown':
            d = p.get('exceptionDetails', {})
            self.problems.append('script error: ' + str((d.get('exception') or {}).get('description') or d.get('text'))[:300])
        elif m == 'Log.entryAdded' and p.get('entry', {}).get('level') in ('error', 'warning'):
            e = p['entry']
            self.problems.append(f"{e['level']} ({e.get('source')}): {e.get('text', '')[:200]} {e.get('url', '')}")

    def js(self, expression: str):
        r = self.call('Runtime.evaluate', expression=expression, returnByValue=True, awaitPromise=True)
        if 'exceptionDetails' in r:
            raise RuntimeError('evaluate failed: ' + json.dumps(r['exceptionDetails'])[:300])
        return r.get('result', {}).get('value')

    def wait_for(self, expression: str, timeout: float = 90, every: float = 0.25) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if self.js(expression):
                return True
            time.sleep(every)
        return False


def start_browser(port: int, profile: str):
    exe = next((b for b in BROWSERS if Path(b).is_file()), None) or shutil.which('msedge') or shutil.which('chrome')
    if not exe:
        sys.exit('No Microsoft Edge or Chrome found.')
    proc = subprocess.Popen([exe, '--headless=new', f'--remote-debugging-port={port}', f'--user-data-dir={profile}',
                             '--no-first-run', '--no-default-browser-check', '--disable-extensions',
                             '--hide-scrollbars', '--remote-allow-origins=*', 'about:blank'],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(80):
        try:
            with urllib.request.urlopen(f'http://127.0.0.1:{port}/json/list', timeout=2) as r:
                pages = [t for t in json.load(r) if t.get('type') == 'page']
            if pages:
                return proc, pages[0]['webSocketDebuggerUrl']
        except OSError:
            pass
        time.sleep(0.25)
    proc.kill()
    sys.exit('The browser did not start its DevTools port.')


# the widest elements, to say what makes a page scroll sideways
OVERFLOW_JS = """(() => {
  const cw = document.documentElement.clientWidth, sw = document.documentElement.scrollWidth;
  if (sw <= cw) return {sw, cw, culprits: []};
  const out = [];
  for (const el of document.querySelectorAll('body *')) {
    const r = el.getBoundingClientRect();
    if (r.right > cw + 1 && r.width > 0) {
      const id = el.id ? '#' + el.id : '', cls = el.classList.length ? '.' + [...el.classList].join('.') : '';
      out.push({el: el.tagName.toLowerCase() + id + cls, right: Math.round(r.right)});
    }
  }
  out.sort((a, b) => b.right - a.right);
  return {sw, cw, culprits: out.slice(0, 5)};
})()"""

# a tab is ready once its view has replaced the old one and stopped changing for a moment
READY_JS = """(() => {
  const v = document.querySelector('#view');
  if (!v || !v.firstElementChild || v.firstElementChild === window.__shotOld) return false;
  const n = v.innerHTML.length;
  if (window.__shotLen === n) { window.__shotSame = (window.__shotSame || 0) + 1; } else { window.__shotSame = 0; window.__shotLen = n; }
  return window.__shotSame >= 4;
})()"""


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('label', help='folder name under data/screenshots, e.g. before or after')
    ap.add_argument('--url', default='http://127.0.0.1:8765/')
    ap.add_argument('--tabs', help='comma-separated tab names (default: every tab)')
    ap.add_argument('--sizes', default='wide,phone', help='wide (1440 px), phone (375 px) or both')
    ap.add_argument('--max-height', type=int, default=4000, help='cut long pages at this many pixels')
    ap.add_argument('--reduced-motion', action='store_true', help='as with prefers-reduced-motion: reduce')
    ap.add_argument('--no-shots', action='store_true', help='only the checks, no pictures')
    ap.add_argument('--port', type=int, default=9339, help='the browser DevTools port')
    args = ap.parse_args()

    out = ROOT / 'data' / 'screenshots' / args.label
    out.mkdir(parents=True, exist_ok=True)
    profile = tempfile.mkdtemp(prefix='wfm-shots-')
    proc, ws_url = start_browser(args.port, profile)
    report, failed = [], False
    try:
        page = Page(ws_url)
        for domain in ('Page', 'Runtime', 'Log'):
            page.call(f'{domain}.enable')
        if args.reduced_motion:
            page.call('Emulation.setEmulatedMedia', features=[{'name': 'prefers-reduced-motion', 'value': 'reduce'}])
        for size in [s.strip() for s in args.sizes.split(',') if s.strip()]:
            w, h, mobile = SIZES[size]
            page.call('Emulation.setDeviceMetricsOverride', width=w, height=h, deviceScaleFactor=1, mobile=mobile)
            page.call('Page.navigate', url=args.url)
            if not page.wait_for("document.readyState === 'complete' && !!document.querySelector('#status')"
                                 " && document.querySelector('#status').textContent.length > 0", timeout=180):
                sys.exit('The page did not load (is the app running?).')
            tabs = args.tabs.split(',') if args.tabs else page.js("[...document.querySelectorAll('#tabs button')].map((b) => b.dataset.tab)")
            for tab in tabs:
                page.problems.clear()
                page.js("window.__shotOld = document.querySelector('#view').firstElementChild; window.__shotLen = -1; true")
                page.js(f"document.querySelector('#tabs button[data-tab=\"{tab}\"]').click(); true")
                ready = page.wait_for(READY_JS, timeout=120)
                page.js('window.scrollTo(0, 0); true')
                time.sleep(0.6)                      # entrance animations and late images
                ov = page.js(OVERFLOW_JS)
                ours = [p for p in page.problems if not any(o in p for o in OUTSIDE)]
                line = {'tab': tab, 'size': size, 'ready': ready, 'sideways_px': ov['sw'] - ov['cw'],
                        'culprits': ov['culprits'], 'problems': ours, 'outside_problems': len(page.problems) - len(ours)}
                if not args.no_shots:
                    height = min(page.js('document.documentElement.scrollHeight'), args.max_height)
                    shot = page.call('Page.captureScreenshot', format='png', captureBeyondViewport=True,
                                     clip={'x': 0, 'y': 0, 'width': ov['cw'], 'height': height, 'scale': 1})
                    path = out / f'{tab}-{size}.png'
                    path.write_bytes(base64.b64decode(shot['data']))
                    line['file'] = str(path.relative_to(ROOT))
                report.append(line)
                bad = line['sideways_px'] > 0 or line['problems'] or not ready
                failed |= bool(bad)
                note = ('' if ready else ' NOT READY') + (f" SIDEWAYS {line['sideways_px']} px {line['culprits']}" if line['sideways_px'] > 0 else '') \
                    + (f" ({line['outside_problems']} errors from Wowhead's tooltip site, not the app)" if line['outside_problems'] else '')
                print(f"{size:5} {tab:9} {'problem' if bad else 'ok':7}{note}")
                for p in line['problems']:
                    print('        ' + p)
    finally:
        proc.kill()
        proc.wait()
        shutil.rmtree(profile, ignore_errors=True)
    (out / 'report.json').write_text(json.dumps(report, indent=1), encoding='utf-8')
    print(f"\n{len(report)} views, {'some problems' if failed else 'no problems'}; pictures and report.json in {out}")
    return 1 if failed else 0


if __name__ == '__main__':
    sys.exit(main())
