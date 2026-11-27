"""Save a batch of Wowhead Forever pages from the browser pane's Wowhead tab to a file, exactly (no copying by hand).

The pane blocks a public page's requests to this PC (fetch from wowhead.com to 127.0.0.1 fails), but the tab may
navigate here. So: run this (it listens on 127.0.0.1 only and stops after one batch or 30 minutes), then in the
Wowhead tab, after the session's last page (navigating away is no Wowhead request):

    const s = localStorage.getItem('wfm_pages_saved_00N');
    location.href = 'http://127.0.0.1:8799/#' + encodeURIComponent(s);

The page served here posts its own URL fragment back (the fragment never leaves this PC) and this saves it, then
prints its length and SHA-256 to check against the tab's. Then `python -m wfm.wowhead_items import <file>`.
Used first on 2026-11-28 (session 9, docs/plans/material-coverage.md).

    python tools/receive_batch.py <out.json>
"""
import hashlib
import sys
from http.server import BaseHTTPRequestHandler, HTTPServer

PORT = 8799
PAGE = b"""<!doctype html><meta charset="utf-8"><title>Batch receiver</title><pre id="o">sending...</pre><script>
const s = decodeURIComponent(location.hash.slice(1));
fetch('/save', {method: 'POST', headers: {'Content-Type': 'text/plain; charset=utf-8'}, body: s})
  .then(r => r.text()).then(t => { document.getElementById('o').textContent = t + ' (' + s.length + ' characters)'; })
  .catch(e => { document.getElementById('o').textContent = 'failed: ' + e; });
</script>"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'text/html; charset=utf-8')
        self.end_headers()
        self.wfile.write(PAGE)

    def do_POST(self):
        body = self.rfile.read(int(self.headers.get('Content-Length') or 0))
        with open(self.server.out, 'wb') as f:
            f.write(body)
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b'saved %d bytes' % len(body))
        print(f'saved {len(body)} bytes to {self.server.out}, SHA-256 {hashlib.sha256(body).hexdigest()}', flush=True)
        self.server.done = True

    def log_message(self, *args):
        pass


def main():
    if len(sys.argv) != 2:
        raise SystemExit('usage: python tools/receive_batch.py <out.json>')
    srv = HTTPServer(('127.0.0.1', PORT), Handler)
    srv.out, srv.done, srv.timeout = sys.argv[1], False, 60
    print(f'waiting on http://127.0.0.1:{PORT}/ (30 minutes at most)', flush=True)
    for _ in range(30):
        srv.handle_request()
        if srv.done:
            return
    print('nothing received', flush=True)


if __name__ == '__main__':
    main()
