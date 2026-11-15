"""The Wowhead Forever page data, shared with friends only: an encrypted pack in the repository, unlocked with a key.

The four local files data/wowhead_forever_*.json are not committed (the repository is public). Instead
data/wowhead_forever.pack holds them, encrypted with a passphrase the author gives to friends (setting `data_key`,
kept in the local data/settings.json, never committed). On start the app unlocks the pack into data/ when the key is
set and the pack holds newer data. Without the key the pack is unreadable and the app runs without that data.

Encryption with the standard library only: key = PBKDF2-HMAC-SHA256(passphrase, random salt, 200,000 rounds, 64
bytes); the first half encrypts (SHA-256 of key, nonce and block counter as a keystream, XORed), the second half
authenticates (HMAC-SHA256 over everything), so a wrong key or a damaged file is refused, never misread.
`python -m wfm.datapack pack` builds the pack from the local files (the pre-commit hook does it when they change).
"""
from __future__ import annotations

import gzip
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path

from .paths import DATA

PACK = DATA / 'wowhead_forever.pack'
FILES = ('wowhead_forever_containers.json', 'wowhead_forever_fishing.json', 'wowhead_forever_items.json',
         'wowhead_forever_skinning.json')
MAGIC = b'WFMPACK1'
ROUNDS = 200_000


class BadKey(ValueError):
    """Wrong key, or the pack is damaged."""


def _keys(passphrase: str, salt: bytes) -> tuple[bytes, bytes]:
    k = hashlib.pbkdf2_hmac('sha256', passphrase.encode('utf-8'), salt, ROUNDS, dklen=64)
    return k[:32], k[32:]


def _stream(key: bytes, nonce: bytes, data: bytes) -> bytes:
    out = bytearray(len(data))
    for block in range(0, len(data), 32):
        ks = hashlib.sha256(key + nonce + (block // 32).to_bytes(8, 'big')).digest()
        chunk = data[block:block + 32]
        out[block:block + len(chunk)] = bytes(a ^ b for a, b in zip(chunk, ks))
    return bytes(out)


def seal(plain: bytes, passphrase: str) -> bytes:
    salt, nonce = os.urandom(16), os.urandom(16)
    enc, mac = _keys(passphrase, salt)
    body = MAGIC + salt + nonce + _stream(enc, nonce, plain)
    return body + hmac.new(mac, body, hashlib.sha256).digest()


def open_sealed(blob: bytes, passphrase: str) -> bytes:
    if len(blob) < len(MAGIC) + 64 or not blob.startswith(MAGIC):
        raise BadKey('not a data pack')
    body, tag = blob[:-32], blob[-32:]
    salt, nonce = body[len(MAGIC):len(MAGIC) + 16], body[len(MAGIC) + 16:len(MAGIC) + 32]
    enc, mac = _keys(passphrase, salt)
    if not hmac.compare_digest(tag, hmac.new(mac, body, hashlib.sha256).digest()):
        raise BadKey('wrong key, or the pack is damaged')
    return _stream(enc, nonce, body[len(MAGIC) + 32:])


def contents(data_dir: Path | None = None) -> dict[str, str]:
    d = data_dir or DATA
    return {f: (d / f).read_text(encoding='utf-8') for f in FILES if (d / f).exists()}


def pack(passphrase: str, data_dir: Path | None = None, path: Path | None = None) -> bool:
    """Write the pack from the local files, only when what they hold changed. Returns True if written."""
    path = path or PACK
    files = contents(data_dir)
    if not files:
        return False
    if path.exists():
        try:
            if json.loads(gzip.decompress(open_sealed(path.read_bytes(), passphrase))) == files:
                return False                    # same data: keep the file (a new pack would differ byte for byte)
        except (BadKey, ValueError, OSError):
            pass
    path.write_bytes(seal(gzip.compress(json.dumps(files).encode('utf-8')), passphrase))
    return True


def unpack(passphrase: str, data_dir: Path | None = None, path: Path | None = None) -> str:
    """Unlock the pack into data/ where it holds something different. Returns what happened (for the log)."""
    d, path = data_dir or DATA, path or PACK
    if not passphrase:
        return 'no data key set'
    if not path.exists():
        return 'no pack'
    try:
        files = json.loads(gzip.decompress(open_sealed(path.read_bytes(), passphrase)))
    except BadKey as e:
        return str(e)
    except (ValueError, OSError):
        return 'the pack could not be read'
    changed = 0
    for name, text in files.items():
        if name in FILES and ((d / name).read_text(encoding='utf-8') if (d / name).exists() else None) != text:
            (d / name).write_text(text, encoding='utf-8')
            changed += 1
    return f'{changed} of {len(files)} files updated' if changed else 'up to date'


if __name__ == '__main__' and sys.argv[1:2] == ['pack']:
    from .settings import Settings
    key = Settings().snapshot().get('data_key') or ''
    print('written' if key and pack(key) else 'unchanged (or no data_key set)')
