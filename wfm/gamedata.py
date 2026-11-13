"""Forever game tables (DB2) from wago.tools, cached per client build, plus derived items and recipes."""
from __future__ import annotations

import csv
import json
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

from .paths import DATA

TABLES = ['ItemSparse', 'Item', 'SkillLine', 'SkillLineAbility', 'SpellEffect', 'SpellReagents', 'SpellName',
          'AreaTable']
USER_AGENT = 'WoWForeverMoney/0.1 (personal gold tool)'
CREATE_ITEM = '24'
ITEM_FLAG_HAS_LOOT = 0x4   # ItemSparse Flags_0: the item can be opened (has its own loot)

# Item class ids (ItemClass.db2)
CLASS_NAMES = {0: 'Consumable', 1: 'Container', 2: 'Weapon', 3: 'Gem', 4: 'Armor', 5: 'Reagent', 6: 'Projectile',
               7: 'Trade Goods', 9: 'Recipe', 11: 'Quiver', 12: 'Quest', 13: 'Key', 15: 'Miscellaneous'}
TRADE_GOODS_SUB = {0: 'Trade Goods', 1: 'Parts', 2: 'Explosives', 3: 'Devices', 4: 'Jewelcrafting', 5: 'Cloth',
                   6: 'Leather', 7: 'Metal & Stone', 8: 'Meat', 9: 'Herb', 10: 'Elemental', 11: 'Other',
                   12: 'Enchanting', 13: 'Materials'}
QUALITY = ['Poor', 'Common', 'Uncommon', 'Rare', 'Epic', 'Legendary', 'Artifact', 'Heirloom']


def _http_get(url: str, timeout: int = 120) -> bytes:
    req = urllib.request.Request(url, headers={'User-Agent': USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def latest_wago_build() -> str | None:
    data = json.loads(_http_get('https://wago.tools/api/builds', 60))
    builds = data.get('wowf') or []
    return builds[0]['version'] if builds else None


def build_dir(build: str) -> Path:
    return DATA / 'gamedata' / build


def ensure_tables(build: str, log=print) -> Path:
    """Download any missing DB2 CSVs for this build. Returns the folder."""
    folder = build_dir(build)
    folder.mkdir(parents=True, exist_ok=True)
    for t in TABLES:
        dest = folder / f'{t}.csv'
        if dest.exists() and dest.stat().st_size > 0:
            continue
        log(f'Downloading {t} for build {build} from wago.tools')
        body = _http_get(f'https://wago.tools/db2/{t}/csv?build={build}')
        if not body.startswith(b'ID') and b',' not in body[:200]:
            raise RuntimeError(f'wago.tools returned something unexpected for {t}')
        tmp = dest.with_suffix('.part')
        tmp.write_bytes(body)
        tmp.replace(dest)
        time.sleep(0.5)  # be polite
    (folder / 'meta.json').write_text(json.dumps({'build': build, 'downloaded': int(time.time())}))
    return folder


def cached_builds() -> list[str]:
    root = DATA / 'gamedata'
    if not root.exists():
        return []
    return sorted((p.name for p in root.iterdir() if (p / 'meta.json').exists()),
                  key=lambda v: [int(x) for x in v.split('.') if x.isdigit()])


def _rows(folder: Path, table: str):
    with open(folder / f'{table}.csv', encoding='utf-8', newline='') as fh:
        yield from csv.DictReader(fh)


def _int(v, default=0) -> int:
    try:
        return int(float(v))
    except (TypeError, ValueError):
        return default


@dataclass
class Item:
    id: int
    name: str
    quality: int
    item_level: int
    req_level: int
    sell_price: int            # copper a vendor pays per item
    buy_price: int             # copper a vendor charges per item (if a vendor sells it)
    stack: int
    class_id: int
    subclass_id: int
    bonding: int
    partial: bool = False      # not in the client's ItemSparse; filled from Wowhead tooltip / Questie
    openable: bool = False     # right-click to open (trunks, clams, lockboxes): worth its contents
    locked: bool = False       # needs Lockpicking (or a key) to open

    @property
    def category(self) -> str:
        if self.class_id == 7:
            return TRADE_GOODS_SUB.get(self.subclass_id, 'Trade Goods')
        return CLASS_NAMES.get(self.class_id, 'Other')


@dataclass
class Recipe:
    spell_id: int
    name: str
    profession: str
    skill_line: int
    product_id: int
    product_count: float
    reagents: list[tuple[int, int]]      # (item id, count)
    trivial_low: int                     # yellow
    trivial_high: int                    # grey
    min_rank: int


@dataclass
class GameData:
    build: str
    items: dict[int, Item] = field(default_factory=dict)
    recipes: list[Recipe] = field(default_factory=list)
    professions: dict[int, str] = field(default_factory=dict)
    zones: dict[int, str] = field(default_factory=dict)
    zone_parent: dict[int, int] = field(default_factory=dict)                 # area id -> parent area id (0 = top level)
    zone_continent: dict[int, int] = field(default_factory=dict)
    item_classes: dict[int, tuple[int, int]] = field(default_factory=dict)   # every item id -> (class, subclass)
    downloaded: int = 0


def load(build: str) -> GameData:
    folder = build_dir(build)
    meta = json.loads((folder / 'meta.json').read_text())
    gd = GameData(build=build, downloaded=meta.get('downloaded', 0))

    classes: dict[int, tuple[int, int]] = {}
    for r in _rows(folder, 'Item'):
        classes[_int(r['ID'])] = (_int(r.get('ClassID')), _int(r.get('SubclassID')))
    gd.item_classes = classes

    for r in _rows(folder, 'ItemSparse'):
        iid = _int(r['ID'])
        stack_count = max(1, _int(r.get('VendorStackCount'), 1))
        cls, sub = classes.get(iid, (-1, -1))
        gd.items[iid] = Item(
            id=iid, name=r.get('Display_lang', ''), quality=_int(r.get('OverallQualityID')),
            item_level=_int(r.get('ItemLevel')), req_level=_int(r.get('RequiredLevel')),
            sell_price=_int(r.get('SellPrice')), buy_price=round(_int(r.get('BuyPrice')) / stack_count),
            stack=_int(r.get('Stackable'), 1), class_id=cls, subclass_id=sub, bonding=_int(r.get('Bonding')),
            openable=bool(_int(r.get('Flags_0')) & ITEM_FLAG_HAS_LOOT), locked=_int(r.get('LockID')) > 0)

    for r in _rows(folder, 'SkillLine'):
        if _int(r.get('CategoryID')) in (9, 11):   # 11 = professions, 9 = secondary skills
            gd.professions[_int(r['ID'])] = r.get('DisplayName_lang', '')

    for r in _rows(folder, 'AreaTable'):
        aid = _int(r['ID'])
        gd.zones[aid] = r.get('AreaName_lang', '')
        gd.zone_parent[aid] = _int(r.get('ParentAreaID'))
        gd.zone_continent[aid] = _int(r.get('ContinentID'))

    names = {_int(r['ID']): r.get('Name_lang', '') for r in _rows(folder, 'SpellName')}
    creates: dict[int, tuple[int, float]] = {}
    for r in _rows(folder, 'SpellEffect'):
        if r.get('Effect') == CREATE_ITEM and _int(r.get('EffectItemType')):
            creates[_int(r['SpellID'])] = (_int(r['EffectItemType']), max(1.0, float(r.get('EffectBasePointsF') or 1)))
    reagents: dict[int, list[tuple[int, int]]] = {}
    for r in _rows(folder, 'SpellReagents'):
        mats = []
        for i in range(8):
            rid, cnt = _int(r.get(f'Reagent_{i}')), _int(r.get(f'ReagentCount_{i}'))
            if rid and cnt:
                mats.append((rid, cnt))
        reagents[_int(r['SpellID'])] = mats

    seen = set()
    for r in _rows(folder, 'SkillLineAbility'):
        line = _int(r.get('SkillLine'))
        if line not in gd.professions:
            continue
        spell = _int(r.get('Spell'))
        if spell not in creates or spell in seen:
            continue
        seen.add(spell)
        product, count = creates[spell]
        gd.recipes.append(Recipe(
            spell_id=spell, name=names.get(spell, ''), profession=gd.professions[line], skill_line=line,
            product_id=product, product_count=count, reagents=reagents.get(spell, []),
            trivial_low=_int(r.get('TrivialSkillLineRankLow')), trivial_high=_int(r.get('TrivialSkillLineRankHigh')),
            min_rank=_int(r.get('MinSkillLineRank'))))
    return gd


def add_partial_item(gd: GameData, iid: int, info: dict | None, fallback_name: str | None) -> Item | None:
    """Create an Item for an id the client's ItemSparse lacks, from tooltip info or just a name."""
    if iid in gd.items:
        return gd.items[iid]
    if not info and not fallback_name:
        return None
    info = info or {}
    cls, sub = gd.item_classes.get(iid, (-1, -1))
    it = Item(id=iid, name=info.get('name') or fallback_name or f'Item {iid}', quality=int(info.get('quality', 1)),
              item_level=int(info.get('item_level', 0)), req_level=int(info.get('req_level', 0)),
              sell_price=int(info.get('sell_price', 0)), buy_price=0, stack=1, class_id=cls, subclass_id=sub,
              bonding=int(info.get('bonding', 0)), partial=True, openable=bool(info.get('openable')))
    gd.items[iid] = it
    return it
