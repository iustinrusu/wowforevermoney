"""Forever item data the client's own tables don't ship: the client's hotfix cache (Cache/ADB/<locale>/DBCache.bin).

WoW: Forever streams many item records from the server instead of shipping them in the client's DB2 files: the
client table has 19,326 of 32,008 items, and the server sent ~6,200 more plus ~1,500 updates to shipped items
(price changes and other fixes). The client stores what it received in DBCache.bin. That is exact Forever data,
straight from Blizzard, so it beats every other source for the items it covers.

File format (version 9): header "XFTH", version, build, 32-byte hash; then entries:
"XFTH", push id, unique id, ?, table hash, record id, data size, status (1 = valid), data.

The record layout (which bytes are which column, and how wide) isn't in the file. It's inferred from the records
that are in both the cache and the client table (wago.tools CSV): every column must reproduce the known values,
so a wrong layout can't pass. The inferred layout is checked on every load (agreement is reported).
"""
from __future__ import annotations

import csv
import json
import math
import struct
from dataclasses import dataclass, field
from pathlib import Path

MAGIC = b'XFTH'
TABLE_HASH = {'ItemSparse': 0x919BE54E, 'Item': 0x50238EC2}
VALID = 1
_INT = {1: '<b', 2: '<h', 4: '<i', 8: '<q'}
_UINT = {1: '<B', 2: '<H', 4: '<I', 8: '<Q'}


@dataclass
class Cache:
    build: int = 0
    version: int = 0
    tables: dict[int, dict[int, tuple[int, bytes]]] = field(default_factory=dict)   # hash -> record id -> (status, data)


def read_cache_build(path: Path) -> int:
    with open(path, 'rb') as fh:
        head = fh.read(12)
    return struct.unpack_from('<I', head, 8)[0] if head[:4] == MAGIC else 0


def read_cache(path: Path) -> Cache:
    b = Path(path).read_bytes()
    if b[:4] != MAGIC:
        raise ValueError('not a DBCache.bin file')
    c = Cache(version=struct.unpack_from('<I', b, 4)[0], build=struct.unpack_from('<I', b, 8)[0])
    pos = 44 if c.version >= 9 else 12
    while pos + 32 <= len(b) and b[pos:pos + 4] == MAGIC:
        _push, _uniq, _x, thash, rid, size, status = struct.unpack_from('<iIIIIII', b, pos + 4)
        c.tables.setdefault(thash, {})[rid] = (status, b[pos + 32:pos + 32 + size])   # later entries win
        pos += 32 + size
    return c


# ---------- layout inference ----------
def _is_string_col(name: str) -> bool:
    return name.endswith('_lang') or name in ('Name', 'Description')


def _matches(raw, text: str) -> bool:
    if isinstance(raw, str):
        return raw == text
    try:
        want = float(text)
    except ValueError:
        return False
    if isinstance(raw, float):
        return math.isclose(raw, want, rel_tol=1e-5, abs_tol=1e-6)
    return raw == want


def _read(blob: bytes, pos: int, kind: str, size: int):
    if kind == 'str':
        end = blob.find(b'\0', pos)
        if end < 0:
            return None, pos
        return blob[pos:end].decode('utf-8', 'replace'), end + 1
    if pos + size > len(blob):
        return None, pos
    fmt = {'int': _INT, 'uint': _UINT, 'float': {4: '<f'}}[kind][size]
    return struct.unpack_from(fmt, blob, pos)[0], pos + size


CANDIDATES = [('int', 4), ('uint', 4), ('float', 4), ('int', 2), ('uint', 2), ('int', 1), ('uint', 1),
              ('int', 8), ('uint', 8)]


def infer_layout(columns: list[str], samples: list[tuple[bytes, dict]], min_agree: float = 0.97) -> list[tuple]:
    """Find (column, kind, size) for every column but ID, so that decoding the sample blobs reproduces the CSV.

    Depth-first over columns in table order. At each column every width that agrees with >= min_agree of the
    samples is a candidate; a column that is 0 in almost every record fits several widths, so candidates are
    ranked by agreement on the records where the value isn't 0, then by the usual 4-byte width. The layout
    must end exactly at the end of the blobs. Fields that still disagree where they're non-zero (the binary
    order can differ from the table's, e.g. PageID/LockID) are reported as unreliable by field_reliability().
    """
    cols = [c for c in columns if c != 'ID']
    n = len(samples)

    def solve(i: int, offsets: list[int]):
        if i == len(cols):
            ok = sum(1 for (blob, _), off in zip(samples, offsets) if off == len(blob))
            return [] if ok >= min_agree * n else None
        col = cols[i]
        cands = [('str', 0)] if _is_string_col(col) else CANDIDATES
        scored = []
        for rank, (kind, size) in enumerate(cands):
            new_offsets, agree, agree_nz, nz = [], 0, 0, 0
            for (blob, row), off in zip(samples, offsets):
                raw, nxt = _read(blob, off, kind, size)
                new_offsets.append(nxt)
                text = row.get(col, '')
                hit = raw is not None and _matches(raw, text)
                agree += hit
                if _nonzero(text):
                    nz += 1
                    agree_nz += hit
            if agree >= min_agree * n:
                scored.append((-(agree_nz / nz if nz else 1.0), -agree, rank, kind, size, new_offsets))
        for *_, kind, size, new_offsets in sorted(scored, key=lambda t: t[:3]):
            rest = solve(i + 1, new_offsets)
            if rest is not None:
                return [(col, kind, size)] + rest
        return None

    import sys
    old = sys.getrecursionlimit()
    sys.setrecursionlimit(max(old, len(cols) * 4 + 100))
    try:
        layout = solve(0, [0] * n)
    finally:
        sys.setrecursionlimit(old)
    if layout is None:
        raise ValueError('could not infer a record layout that reproduces the client table')
    return layout


def _nonzero(text: str) -> bool:
    try:
        return float(text) != 0
    except ValueError:
        return bool(text)


def decode(blob: bytes, layout: list[tuple]) -> dict | None:
    out, pos = {}, 0
    for col, kind, size in layout:
        raw, pos = _read(blob, pos, kind, size)
        if raw is None:
            return None
        out[col] = raw
    return out if pos == len(blob) else None


def table_rows(csv_path: Path) -> tuple[list[str], dict[int, dict]]:
    with open(csv_path, encoding='utf-8', newline='') as fh:
        r = csv.DictReader(fh)
        rows = {int(row['ID']): row for row in r}
        return list(r.fieldnames or []), rows


def field_reliability(layout, overlap: list[tuple[bytes, dict]]) -> dict[str, tuple[int, int]]:
    """column -> (records where the client value isn't 0, of those how many decode to it)."""
    stats = {c: [0, 0] for c, _, _ in layout}
    for blob, row in overlap:
        dec = decode(blob, layout)
        if dec is None:
            continue
        for c, raw in dec.items():
            if _nonzero(row.get(c, '')):
                stats[c][0] += 1
                stats[c][1] += _matches(raw, row.get(c, ''))
    return {c: (nz, ok) for c, (nz, ok) in stats.items()}


@dataclass
class HotfixItems:
    rows: dict[int, dict] = field(default_factory=dict)      # item id -> decoded ItemSparse columns (reliable only)
    layout: list = field(default_factory=list)
    agreement: float = 0.0          # share of overlapping records whose decode reproduces the client table exactly
    new_items: int = 0
    updated_items: int = 0
    changed_fields: dict[str, int] = field(default_factory=dict)   # column -> how many shipped items the server changed
    unreliable: list[str] = field(default_factory=list)              # columns not trusted (left out of rows)
    cache_build: int = 0
    inferred: bool = False          # True if the layout was inferred on this load (else the saved one was verified)


UNRELIABLE_NZ = 0.9


def load_item_hotfixes(cache_path: Path, csv_path: Path, layout_file: Path | None = None,
                       sample_size: int = 2000) -> HotfixItems:
    cache = read_cache(cache_path)
    recs = {rid: data for rid, (status, data) in cache.tables.get(TABLE_HASH['ItemSparse'], {}).items()
            if status == VALID and data}
    columns, client = table_rows(csv_path)
    overlap_ids = sorted(i for i in recs if i in client)
    overlap = [(recs[i], client[i]) for i in overlap_ids]
    layout, inferred = None, False
    if layout_file and Path(layout_file).exists():
        try:
            saved = json.loads(Path(layout_file).read_text(encoding='utf-8'))
            layout = [tuple(x) for x in saved.get('layout', [])]
        except (OSError, ValueError):
            layout = None
    out = HotfixItems(cache_build=cache.build)

    def agreement(lay):
        exact = 0
        for blob, row in overlap:
            dec = decode(blob, lay)
            exact += dec is not None and all(_matches(raw, row.get(c, '')) for c, raw in dec.items())
        return exact / len(overlap) if overlap else 0.0

    if layout:
        out.agreement = agreement(layout)
    if not layout or out.agreement < 0.95:      # no saved layout, or the game changed it: infer again
        step = max(1, len(overlap) // sample_size)
        layout = infer_layout(columns, overlap[::step])
        out.agreement, inferred = agreement(layout), True
        if layout_file:
            Path(layout_file).write_text(json.dumps({'layout': layout, 'build': cache.build}), encoding='utf-8')
    out.layout, out.inferred = layout, inferred
    rel = field_reliability(layout, overlap)
    changed = {}
    for blob, row in overlap:
        dec = decode(blob, layout)
        for c, raw in (dec or {}).items():
            if not _matches(raw, row.get(c, '')):
                changed[c] = changed.get(c, 0) + 1
    # Unreliable: wrong where the client value isn't 0, or "changed" on more records than it is ever non-zero
    # (a mostly-zero field reading other bytes, e.g. LockID on letters, rather than real server changes).
    out.unreliable = sorted(c for c, (nz, ok) in rel.items()
                            if (nz >= 3 and ok / nz < UNRELIABLE_NZ) or changed.get(c, 0) >= max(5, nz + 1))
    out.changed_fields = {c: k for c, k in sorted(changed.items(), key=lambda kv: -kv[1]) if c not in out.unreliable}
    for i, blob in recs.items():
        dec = decode(blob, layout)
        if dec is not None:
            out.rows[i] = {c: v for c, v in dec.items() if c not in out.unreliable}
    out.new_items = sum(1 for i in out.rows if i not in client)
    out.updated_items = sum(1 for i in out.rows if i in client)
    return out
