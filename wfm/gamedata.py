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
          'AreaTable', 'SpellCooldowns', 'SpellCategories', 'SpellCategory', 'UiMap', 'UiMapAssignment',
          'ItemEffect', 'ItemXItemEffect',      # what an item does when used (the Salt Shaker), and its cooldown
          'SpellTotems', 'TotemCategory']       # tools a recipe needs (Philosopher's Stone, Blacksmith Hammer)
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
    req_skill: int = 0         # profession (SkillLine id) needed to use it, e.g. Leatherworking for the Salt Shaker
    req_skill_rank: int = 0    # and the skill in it
    totem_category: int = 0    # the kind of tool it counts as (TotemCategory: Blacksmith Hammer, Runed Arcanite Rod)
    sell_from_tsm: bool = False   # sell_price is TSM's VendorSell, read in game (apply_tsm_vendor)

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
    tool_id: int = 0                     # made by using an item you keep (the Salt Shaker), not a recipe you learn
    use_item: int = 0                    # made by using an item that is used up or combined (essences, Darkmoon cards)
    tool_charges: int = 0                # uses the tool has before it is gone (0 = unlimited)
    tools_needed: tuple = ()             # TotemCategory ids the recipe needs in your bags (SpellTotems)
    tool_items: tuple = ()               # specific items the recipe needs in your bags (SpellTotems)


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
    totem_categories: dict[int, tuple] = field(default_factory=dict)          # id -> (name, type, mask)
    # every other spell that makes an item, and why it is not a recipe here: (spell, name, product, count, reagents,
    # how it is cast). interactions.py reports them, so a gap like the Salt Shaker shows up by itself.
    other_creates: list[tuple] = field(default_factory=list)


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
            openable=bool(_int(r.get('Flags_0')) & ITEM_FLAG_HAS_LOOT), locked=_int(r.get('LockID')) > 0,
            req_skill=_int(r.get('RequiredSkill')), req_skill_rank=_int(r.get('RequiredSkillRank')),
            totem_category=_int(r.get('TotemCategoryID')))

    line_names: dict[int, str] = {}
    for r in _rows(folder, 'SkillLine'):
        line_names[_int(r['ID'])] = r.get('DisplayName_lang', '')
        if _int(r.get('CategoryID')) in (9, 11):   # 11 = professions, 9 = secondary skills
            gd.professions[_int(r['ID'])] = r.get('DisplayName_lang', '')

    for r in _rows(folder, 'AreaTable'):
        aid = _int(r['ID'])
        gd.zones[aid] = r.get('AreaName_lang', '')
        gd.zone_parent[aid] = _int(r.get('ParentAreaID'))
        gd.zone_continent[aid] = _int(r.get('ContinentID'))

    names = {_int(r['ID']): r.get('Name_lang', '') for r in _rows(folder, 'SpellName')}
    creates: dict[int, tuple[int, float]] = {}
    triggered: set[int] = set()                    # spells another spell casts
    for r in _rows(folder, 'SpellEffect'):
        if r.get('Effect') == CREATE_ITEM and _int(r.get('EffectItemType')):
            creates[_int(r['SpellID'])] = (_int(r['EffectItemType']), max(1.0, float(r.get('EffectBasePointsF') or 1)))
        if _int(r.get('EffectTriggerSpell')):
            triggered.add(_int(r.get('EffectTriggerSpell')))
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
    any_line: dict[int, int] = {}                  # every spell a skill line teaches (class skills too)
    for r in _rows(folder, 'SkillLineAbility'):
        line = _int(r.get('SkillLine'))
        any_line.setdefault(_int(r.get('Spell')), line)
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
    gd.recipes.extend(item_use_recipes(folder, gd, creates, reagents, names, seen))
    add_tools_needed(folder, gd)
    in_recipes = {r.spell_id for r in gd.recipes}
    item_uses = _item_use_spells(folder)
    for spell, (product, count) in creates.items():
        if spell in in_recipes:
            continue
        if spell in any_line:
            how = f'class or other skill: {line_names.get(any_line[spell], any_line[spell])}'
        elif spell in item_uses:
            how = ('item use left out (it turns an item into itself, or makes something from nothing with under 10 '
                   'minutes between uses)')
        elif spell in triggered:
            how = 'cast by another spell'
        else:
            how = 'no player source in the game data (an NPC, object or quest casts it)'
        gd.other_creates.append((spell, names.get(spell, ''), product, count, reagents.get(spell, []), how))
    shared: dict[str, int] = {}
    for rec in gd.recipes:
        if rec.cooldown_group:
            shared[rec.cooldown_group] = shared.get(rec.cooldown_group, 0) + 1
    for rec in gd.recipes:      # a category used by a single recipe isn't shared with anything
        if rec.cooldown_group and shared[rec.cooldown_group] < 2:
            rec.cooldown_group = ''
    return gd


NO_PROFESSION = 'No profession'


def item_use_recipes(folder: Path, gd: GameData, creates: dict, reagents: dict, names: dict,
                     recipe_spells: set) -> list[Recipe]:
    """Things made by using an item, not by a recipe you learn (ItemEffect with trigger 0 = on use, whose spell creates
    an item). These are not in SkillLineAbility, so the app never saw them until the user asked about the Salt Shaker
    and Cured Rugged Hide (2026-11-19). Three kinds, from ItemEffect.Charges:
    - a tool you keep (Charges 0, the item is not a reagent): the Salt Shaker (Leatherworking 250) turns 1 Deeprock
      Salt into 1 Refined Deeprock Salt, once every 71 hours (the Forever tooltip says "2 Days, 23 Hrs Cooldown");
      the Snowmaster 9000 (Engineering). Charges above 0: a tool with that many uses (Graverobber's Shovel, 20).
    - an item used up (Charges -1): it counts as one more reagent. Lesser Magic Essence: 1 used + 2 reagents = "Turn
      three lesser magic essences into a greater one" (Forever tooltip); Greater Magic Essence: "into three lesser
      ones" (creates 3).
    - items combined (Charges 0, the item is one of the reagents): eight Darkmoon cards into a deck, map fragments.
    The profession is the one the item needs to be used (RequiredSkill), else NO_PROFESSION. They give no skill-ups.
    Left out: a use that only turns an item into itself, and a free use (no reagents, nothing used up) without a
    cooldown of 10+ minutes."""
    if not ((folder / 'ItemEffect.csv').exists() and (folder / 'ItemXItemEffect.csv').exists()):
        return []                                   # older caches get the tables on the next start
    effects = {_int(r['ID']): r for r in _rows(folder, 'ItemEffect') if _int(r.get('TriggerType')) == 0}
    out, seen = [], set(recipe_spells)
    for link in _rows(folder, 'ItemXItemEffect'):
        used, e = _int(link.get('ItemID')), effects.get(_int(link.get('ItemEffectID')))
        it = gd.items.get(used)
        if not e or not it:
            continue
        spell, charges = _int(e.get('SpellID')), _int(e.get('Charges'))
        if spell not in creates or spell in seen:
            continue
        product, count = creates[spell]
        mats = list(reagents.get(spell) or [])
        cooldown = max(_int(e.get('CoolDownMSec')), _int(e.get('CategoryCoolDownMSec')), 0)
        tool = use_item = 0
        if charges < 0:                              # used up: one more of it is consumed
            use_item = used
            mats = [(m, c + 1) if m == used else (m, c) for m, c in mats]
            if not any(m == used for m, _ in mats):
                mats.append((used, 1))
        elif any(m == used for m, _ in mats):         # combined with the others (Darkmoon cards)
            use_item = used
        else:                                         # a tool you keep (or one with a few charges)
            tool = used
        if not mats and cooldown < 600_000:
            continue                                  # something from nothing, as often as you like: not real
        if [m for m, _ in mats] == [product]:
            continue                                  # an item turned into itself (Heavy Leather Ball)
        seen.add(spell)
        prof = gd.professions.get(it.req_skill, NO_PROFESSION)
        out.append(Recipe(
            spell_id=spell, name=names.get(spell, '') or it.name, profession=prof, skill_line=it.req_skill,
            product_id=product, product_count=count, reagents=mats, trivial_low=0, trivial_high=0,
            min_rank=max(1, it.req_skill_rank), cooldown_ms=cooldown, tool_id=tool, use_item=use_item,
            tool_charges=max(0, charges) if tool else 0))
    return out


def _item_use_spells(folder: Path) -> set[int]:
    if not (folder / 'ItemEffect.csv').exists():
        return set()
    return {_int(r.get('SpellID')) for r in _rows(folder, 'ItemEffect') if _int(r.get('TriggerType')) == 0}


def add_tools_needed(folder: Path, gd: GameData) -> None:
    """The tools a recipe needs in your bags (SpellTotems): a kind of tool (TotemCategory, e.g. Philosopher's Stone for
    transmutes, Blacksmith Hammer, Runed Arcanite Rod) or a specific item (Flint and Tinder). Not used up."""
    if not ((folder / 'SpellTotems.csv').exists() and (folder / 'TotemCategory.csv').exists()):
        return
    gd.totem_categories = {_int(r['ID']): (r.get('Name_lang', ''), _int(r.get('TotemCategoryType')),
                                            _int(r.get('TotemCategoryMask'))) for r in _rows(folder, 'TotemCategory')}
    need: dict[int, tuple[tuple, tuple]] = {}
    for r in _rows(folder, 'SpellTotems'):
        cats = tuple(c for c in (_int(r.get('RequiredTotemCategoryID_0')), _int(r.get('RequiredTotemCategoryID_1'))) if c)
        items = tuple(i for i in (_int(r.get('Totem_0')), _int(r.get('Totem_1'))) if i)
        if cats or items:
            need[_int(r.get('SpellID'))] = (cats, items)
    for rec in gd.recipes:
        if rec.spell_id in need:
            rec.tools_needed, rec.tool_items = need[rec.spell_id]


def tool_fits(gd: GameData, have_category: int, need_category: int) -> bool:
    """Does an item of one tool kind count as another (TotemCategory: same type, and its mask holds the needed mask)?
    A Gnomish Army Knife counts as a Blacksmith Hammer, Mining Pick and Skinning Knife; a Runed Arcanite Rod as every
    lower rod."""
    if have_category == need_category:
        return True
    have, need = gd.totem_categories.get(have_category), gd.totem_categories.get(need_category)
    return bool(have and need and have[1] == need[1] and (have[2] & need[2]) == need[2])


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


def apply_tsm_vendor(gd: GameData, tsm_vendor: dict) -> dict:
    """TSM's VendorSell, read in game by ForeverMoneyBridge 1.6.2 (TSM takes it from the game client): what a vendor
    pays for each item. It wins over the game files for items your client hasn't checked (the user, 2026-11-19: "TSM
    should be the king when it comes to pricing data"; the hotfix cache's prices for new items were wrong 91% of the
    time). Your client's own check (apply_ingame, run first) still wins: TSM keeps an item's price in its own saved item
    info, and on 2026-11-19 it was 5% low for 3 items a server hotfix had changed (Grovekeeper Leggings: 33,997 vs
    35,696), while it matched your client on the other 2,966 checked. Returns counts, the unchecked items whose file
    price differed (`differ`), and how TSM compared with your client (`client_same`, `client_differ` with the check's
    time) for Data health and the in-game check queue."""
    sells = (tsm_vendor or {}).get('sell') or {}
    n, differ, client_same, client_differ = 0, [], 0, []
    for iid, v in sells.items():
        try:
            iid, v = int(iid), int(v)
        except (TypeError, ValueError):
            continue
        it = gd.items.get(iid)
        if it is None or v <= 0:
            continue
        if it.source == 'in-game':
            if it.sell_price == v:
                client_same += 1
            else:
                client_differ.append((iid, it.name, it.sell_price, v, int((it.checked or {}).get('at') or 0)))
        elif it.sell_price != v:
            differ.append((iid, it.name, it.sell_price, v, it.source))
        if it.source != 'in-game':
            it.sell_price = v
            it.untrusted = tuple(f for f in it.untrusted if f != 'sell_price')
        it.sell_from_tsm = True
        n += 1
    return {'sell': n, 'buy': len((tsm_vendor or {}).get('buy') or {}), 'differ': differ,
            'client_same': client_same, 'client_differ': client_differ, 'at': (tsm_vendor or {}).get('at')}


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
