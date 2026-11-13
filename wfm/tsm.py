"""Parse TradeSkillMaster_AppHelper/AppData.lua written by the TSM desktop app.

Each line looks like:
  select(2, ...).LoadData("AUCTIONDB_NON_COMMODITY_DATA","PvP-Horde",[[return {downloadTime=..,fields={..},data={{..},..}}]]) --<..>
Item ids are plain decimal (or quoted item strings); every other number is base-32 (0-9, A-V).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_LOAD = re.compile(r'LoadData\("([A-Z_]+)","([^"]*)",\[\[return \{(.*)\}\]\]\)')
_DOWNLOAD = re.compile(r'downloadTime=(\d+)')
_FIELDS = re.compile(r'fields=\{([^}]*)\}')
_ROW = re.compile(r'\{([^{}]*)\}')

# Fields TSM stores scaled; divide to get the natural unit.
SCALE = {
    'regionSalePercent': 1000.0,    # -> fraction 0..1 (sale rate); raw values top out at 1000
    'regionSoldPerDay': 1000.0,     # -> items per day
}


def b32(token: str) -> int:
    return int(token, 32) if token else 0


def parse_item_string(token: str) -> int | None:
    token = token.strip().strip('"')
    if token.isdigit():
        return int(token)
    m = re.match(r'i:(\d+)', token)
    return int(m.group(1)) if m else None


@dataclass
class Dataset:
    kind: str
    scope: str            # realm name or region name
    download_time: int
    fields: list[str]
    rows: dict[int, dict[str, float]] = field(default_factory=dict)


@dataclass
class PriceData:
    datasets: list[Dataset]
    app_info: dict = field(default_factory=dict)

    def realms(self) -> list[str]:
        return sorted({d.scope for d in self.datasets if d.kind.startswith('AUCTIONDB_NON_COMMODITY')})

    def region(self) -> str | None:
        return next((d.scope for d in self.datasets if d.kind.startswith('AUCTIONDB_REGION')), None)

    def merged(self, realm: str | None) -> dict[int, dict[str, float]]:
        """One dict per item with every field from the region datasets plus the chosen realm's."""
        region = self.region()
        out: dict[int, dict[str, float]] = {}
        for d in self.datasets:
            if d.scope == region or (realm and d.scope == realm):
                for item_id, vals in d.rows.items():
                    out.setdefault(item_id, {}).update(vals)
        return out

    def times(self) -> dict[str, int]:
        return {f'{d.kind}:{d.scope}': d.download_time for d in self.datasets}


def parse_appdata(path: Path) -> PriceData:
    datasets: list[Dataset] = []
    app_info: dict = {}
    text = path.read_text(encoding='utf-8', errors='replace')
    for line in text.splitlines():
        m = _LOAD.search(line)
        if not m:
            continue
        kind, scope, body = m.groups()
        if kind == 'APP_INFO':
            lm = re.search(r'lastSync=(\d+)', body)
            if lm:
                app_info['lastSync'] = int(lm.group(1))
            continue
        dm, fm = _DOWNLOAD.search(body), _FIELDS.search(body)
        if not fm:
            continue
        fields = [f.strip().strip('"') for f in fm.group(1).split(',') if f.strip()]
        ds = Dataset(kind, scope, int(dm.group(1)) if dm else 0, fields)
        data_start = body.find('data={')
        if data_start < 0:
            continue
        for row in _ROW.finditer(body, data_start + 6):
            parts = row.group(1).split(',')
            if len(parts) != len(fields):
                continue
            item_id = parse_item_string(parts[0])
            if item_id is None:
                continue
            is_variant = not parts[0].strip().strip('"').isdigit()
            if is_variant and item_id in ds.rows:
                continue   # keep the plain item's row; variants (e.g. "i:123::i1") are rare level/bonus versions
            vals = {}
            for name, tok in zip(fields[1:], parts[1:]):
                v = b32(tok.strip())
                vals[name] = v / SCALE[name] if name in SCALE else v
            ds.rows[item_id] = vals
        datasets.append(ds)
    return PriceData(datasets, app_info)
