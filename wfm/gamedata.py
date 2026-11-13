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
          'AreaTable', 'SpellCooldowns', 'SpellCategories', 'SpellCategory']
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
    source: str = 'client'     # client (game tables) | server / server-new (hotfix cache: update / item only it has) | wowhead | questie | in-game
    checked: dict | None = None   # once verified in game: {'against': previous source, 'differs': [fields]}
    untrusted: tuple = ()      # fields of this item's source that in-game checks show are often wrong

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
    cooldown_ms: int = 0                 # SpellCooldowns (e.g. Transmute: Arcanite 47 h, Mooncloth 95 h)
    cooldown_group: str = ''             # shared cooldown (SpellCategories), e.g. 'Transmute - Alchemy'


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
    hotfix_items: int = 0          # items taken from the server's data (client hotfix cache)
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

    cooldowns: dict[int, int] = {}
    if (folder / 'SpellCooldowns.csv').exists():          # older caches get it on the next start
        for r in _rows(folder, 'SpellCooldowns'):
            if _int(r.get('DifficultyID')) == 0:
                ms = max(_int(r.get('CategoryRecoveryTime')), _int(r.get('RecoveryTime')))
                if ms:
                    sid = _int(r.get('SpellID'))
                    cooldowns[sid] = max(cooldowns.get(sid, 0), ms)

    # a category cooldown is shared: casting one spell of the category starts the cooldown for all of them
    # (verified 2026-11-14: every Forever transmute is in category 310 'Transmute - Alchemy')
    groups: dict[int, str] = {}
    if (folder / 'SpellCategories.csv').exists() and (folder / 'SpellCategory.csv').exists():
        cat_names = {_int(r['ID']): r.get('Name_lang', '') for r in _rows(folder, 'SpellCategory')}
        for r in _rows(folder, 'SpellCategories'):
            cat = _int(r.get('Category'))
            if cat and _int(r.get('DifficultyID')) == 0:
                groups[_int(r.get('SpellID'))] = cat_names.get(cat) or f'category {cat}'

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
            min_rank=_int(r.get('MinSkillLineRank')), cooldown_ms=cooldowns.get(spell, 0),
            cooldown_group=groups.get(spell, '') if cooldowns.get(spell, 0) else ''))
    shared: dict[str, int] = {}
    for rec in gd.recipes:
        if rec.cooldown_group:
            shared[rec.cooldown_group] = shared.get(rec.cooldown_group, 0) + 1
    for rec in gd.recipes:      # a category used by a single recipe isn't shared with anything
        if rec.cooldown_group and shared[rec.cooldown_group] < 2:
            rec.cooldown_group = ''
    return gd


# Classic dungeon, raid and battleground map ids (AreaTable ContinentID). Forever's new open-world zones sit on new
# continents (Zephras Isle 2991, Storm Cliffs 2791), so "not Eastern Kingdoms or Kalimdor" is not "instance".
INSTANCE_MAPS = {30, 33, 34, 36, 43, 47, 48, 70, 90, 109, 129, 189, 209, 229, 230, 249, 289, 309, 329, 349, 389,
                 409, 429, 469, 489, 509, 529, 531, 533}


def is_instance(gd: GameData, zone_id: int) -> bool:
    return gd.zone_continent.get(zone_id, 0) in INSTANCE_MAPS


def apply_hotfixes(gd: GameData, rows: dict[int, dict]) -> dict:
    """Overlay the server's item data (client hotfix cache, see hotfix.py) on the client tables: it is newer for
    the items it covers, and it adds items the client tables don't ship. Returns counts."""
    added = updated = 0
    for iid, r in rows.items():
        stack_count = max(1, _int(r.get('VendorStackCount'), 1))
        cls, sub = gd.item_classes.get(iid, (-1, -1))
        old = gd.items.get(iid)
        item = Item(
            id=iid, name=str(r.get('Display_lang') or (old.name if old else '')), quality=_int(r.get('OverallQualityID')),
            item_level=_int(r.get('ItemLevel')), req_level=_int(r.get('RequiredLevel')),
            sell_price=_int(r.get('SellPrice')), buy_price=round(_int(r.get('BuyPrice')) / stack_count),
            stack=_int(r.get('Stackable'), 1), class_id=cls, subclass_id=sub, bonding=_int(r.get('Bonding')),
            openable=bool(_int(r.get('Flags_0')) & ITEM_FLAG_HAS_LOOT),
            locked=(_int(r['LockID']) > 0) if 'LockID' in r else bool(old and old.locked),
            # graded separately by in-game checks: new items' sell prices proved unreliable, updates' didn't
            source='server' if (old and not old.partial) else 'server-new')
        if not item.name:
            continue
        if old and not old.partial:
            updated += 1
        else:
            added += 1
        gd.items[iid] = item
    gd.hotfix_items = added + updated
    return {'added': added, 'updated': updated}


INGAME_FIELDS = {'s': 'sell_price', 'q': 'quality', 'l': 'item_level', 'r': 'req_level', 'k': 'stack', 'b': 'bonding'}


def apply_ingame(gd: GameData, info: dict) -> int:
    """Overlay what your own game client reported for items (ForeverMoneyBridge item checks): the ground truth.
    The first time an item is verified, which fields its previous source got wrong is kept in item.checked."""
    n = 0
    for iid, r in (info or {}).items():
        try:
            iid = int(iid)
        except (TypeError, ValueError):
            continue
        if not isinstance(r, dict) or not r.get('n'):
            continue
        it = gd.items.get(iid)
        if it is None:
            cls, sub = gd.item_classes.get(iid, (_int(r.get('c'), -1), _int(r.get('sc'), -1)))
            it = gd.items[iid] = Item(id=iid, name=str(r['n']), quality=0, item_level=0, req_level=0, sell_price=0,
                                      buy_price=0, stack=1, class_id=cls, subclass_id=sub, bonding=0, partial=True,
                                      source='none')
        if it.source != 'in-game':
            differs = [attr for key, attr in INGAME_FIELDS.items() if r.get(key) is not None and getattr(it, attr) != _int(r[key])]
            it.checked = {'against': it.source, 'differs': differs, 'at': _int(r.get('t'))}
        for key, attr in INGAME_FIELDS.items():
            if r.get(key) is not None:
                setattr(it, attr, _int(r[key]))
        it.name = str(r['n']) or it.name
        it.source = 'in-game'
        n += 1
    return n


TRUST_MIN_CHECKS = 30     # grade a source's field once the game has checked this many of its items
TRUST_MAX_WRONG = 0.2      # wrong more often than this: not trusted for that source's unchecked items


def grade_sources(gd: GameData) -> dict[tuple[str, str], dict]:
    """How often each source's fields matched your game client (ForeverMoneyBridge item checks).

    (source, field) -> {'checked', 'wrong', 'rate', 'trusted'}. Found 2026-11-14: the hotfix cache's sell price
    for new Forever items was wrong for 310 of 356 checked items, while every other field matched.
    """
    counts: dict[tuple[str, str], list] = {}
    for it in gd.items.values():
        c = it.checked
        if not c:
            continue
        for attr in INGAME_FIELDS.values():
            k = counts.setdefault((c['against'], attr), [0, 0])
            k[0] += 1
            k[1] += attr in c.get('differs', ())
    out = {}
    for (src, attr), (n, wrong) in counts.items():
        rate = wrong / n if n else 0.0
        out[(src, attr)] = {'checked': n, 'wrong': wrong, 'rate': rate,
                            'trusted': not (n >= TRUST_MIN_CHECKS and rate > TRUST_MAX_WRONG)}
    return out


def mark_untrusted(gd: GameData, grades: dict[tuple[str, str], dict]) -> int:
    """Mark unchecked items whose source is unreliable for a field. Returns how many items were marked."""
    bad: dict[str, tuple] = {}
    for (src, attr), g in grades.items():
        if not g['trusted']:
            bad[src] = bad.get(src, ()) + (attr,)
    n = 0
    for it in gd.items.values():
        it.untrusted = () if it.source == 'in-game' else bad.get(it.source, ())
        n += bool(it.untrusted)
    return n


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
              bonding=int(info.get('bonding', 0)), partial=True, openable=bool(info.get('openable')),
              source='wowhead' if info.get('name') or info.get('sell_price') else 'questie')
    gd.items[iid] = it
    return it
