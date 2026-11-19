"""Read the generated data tables shipped with the SkillUpForever addon: optional since 2026-11-19 (the user: "make
skillupforever optional so I can delete the addon"). ForeverRecipes is the main recipe source (foreverrecipes.merged);
when installed, SkillUpForever fills its gaps (a required skill it doesn't know, limited stock at other vendors, the
profession ranks) and cross-checks the recipes we derive from wago.tools. SkillUpData is also the shape of the merged
recipe facts the engine reads (world.skillup).
"""
from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path

from .lua import parse_assignments
from .paths import DATA

# A copy of the tables, saved while the addon is installed, used once it is deleted (the user, 2026-11-19: "make
# skillupforever optional so I can delete the addon"). Without it, stock limits at herb and other vendors were lost and
# 40 crafts looked up to 10 times better (Elixir of Shadow Power: 1g 55s a day -> 11g 69s). The tables are generated
# from the WoW Classic database and the game files and don't change; the copy stays local (data/, never committed).
SAVED = DATA / 'skillup_saved.json'
SAVED_FIELDS = ('thresholds', 'trainer_fees', 'limited_stock', 'vendor_prices', 'recipe_scrolls', 'rank_trainers',
                'rank_books', 'rank_quests', 'profession_trainers')


@dataclass
class SkillUpData:
    thresholds: dict[int, list[int]] = field(default_factory=dict)     # recipe spell -> [orange, yellow, green, grey]
    trainer_fees: dict[int, list[int]] = field(default_factory=dict)   # recipe spell -> [fee copper, required skill]
    limited_stock: dict[int, dict[int, int]] = field(default_factory=dict)  # item -> {npc: stock}
    vendor_prices: dict[int, int] = field(default_factory=dict)        # item -> copper per unit
    recipe_data: dict[int, dict] = field(default_factory=dict)         # recipe spell -> {skillLine, reagents, output}
    recipe_scrolls: dict = field(default_factory=dict)   # {recipe spell: [item, skill]} (older: {item: spell})
    source_build: str | None = None
    # filled by foreverrecipes.merged (the second recipe source): spells whose required skill is exact, the character
    # level a recipe needs, and the spells whose colours came from ForeverRecipes
    requirement_known: set = field(default_factory=set)
    level_required: dict[int, int] = field(default_factory=dict)
    from_forever_recipes: set = field(default_factory=set)
    from_skillup: set = field(default_factory=set)              # required skill filled in by SkillUpForever
    # profession ranks above Apprentice (Journeyman, Expert, Artisan), by skill line. SkillUpForever generates these
    # from the WoW Classic database (CMaNGOS classic-db npc_trainer, quest_template: base fees before reputation
    # discounts), the books from the game files: the app labels them "Classic database" (A3, 2026-11-19).
    rank_trainers: dict[int, list] = field(default_factory=dict)  # line -> [(cap, fee copper, required skill, level)]
    rank_books: dict[int, list] = field(default_factory=dict)     # line -> [(cap, book item, list price, skill, level)]
    rank_quests: dict[int, list] = field(default_factory=dict)    # line -> [(cap, quest, skill, level, side 'A'/'H')]
    profession_trainers: dict[int, list] = field(default_factory=dict)   # line -> [(npc, highest cap it teaches)]


def _load(path: Path) -> tuple[dict, str]:
    if not path.exists():
        return {}, ''
    text = path.read_text(encoding='utf-8', errors='replace')
    return parse_assignments(text), text


def load_skillup(data_dir: Path) -> SkillUpData:
    out = SkillUpData()
    th, text = _load(data_dir / 'Thresholds.lua')
    out.thresholds = th.get('Thresholds', {}) or {}
    m = re.search(r'wow_classic_beta ([\d.]+)', text)
    out.source_build = m.group(1) if m else None
    tr, _ = _load(data_dir / 'Trainer.lua')
    out.trainer_fees = tr.get('TrainerFees', {}) or {}
    out.rank_trainers = _rows(tr.get('TrainerRanks'), 4)
    out.rank_quests = _rows(tr.get('RankQuests'), 5)
    src, _ = _load(data_dir / 'Sources.lua')
    out.limited_stock = src.get('LimitedStock', {}) or {}
    out.profession_trainers = _rows(src.get('ProfessionTrainers'), 2)
    ven, _ = _load(data_dir / 'Vendor.lua')
    out.vendor_prices = ven.get('VendorPrices', {}) or {}
    rec, _ = _load(data_dir / 'Recipes.lua')
    out.recipe_data = rec.get('RecipeData', {}) or {}
    out.recipe_scrolls = rec.get('RecipeScrolls', {}) or {}
    out.rank_books = _rows(rec.get('RankBooks'), 5)
    return out


def _ints(d):
    """JSON gives string keys back: numbers again, all the way down."""
    if isinstance(d, dict):
        return {(int(k) if isinstance(k, str) and k.lstrip('-').isdigit() else k): _ints(v) for k, v in d.items()}
    if isinstance(d, list):
        return [_ints(v) for v in d]
    return d


def save_copy(su: SkillUpData, version: str | None = None, path: Path = SAVED) -> bool:
    """Save the tables the app uses (not recipe_data: only a cross-check) for when the addon is gone."""
    if not su.thresholds:
        return False
    body = {'saved': time.strftime('%Y-%m-%d'), 'version': version, 'source_build': su.source_build,
            **{f: getattr(su, f) for f in SAVED_FIELDS}}
    text = json.dumps(body, separators=(',', ':'))
    try:
        old = json.loads(path.read_text(encoding='utf-8')) if path.exists() else {}
        if old and {k: v for k, v in old.items() if k != 'saved'} == {k: v for k, v in json.loads(text).items()
                                                                      if k != 'saved'}:
            return False                          # unchanged: keep the date it was first saved
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding='utf-8')
        return True
    except (OSError, ValueError):
        return False


def load_copy(path: Path = SAVED) -> tuple[SkillUpData | None, dict]:
    """The saved tables, and {'saved': date, 'version': addon version} (None when there is no copy)."""
    try:
        body = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return None, {}
    out = SkillUpData(source_build=body.get('source_build'))
    for f in SAVED_FIELDS:
        v = _ints(body.get(f) or {})
        if f.startswith('rank_') or f == 'profession_trainers':
            v = {k: [tuple(r) for r in rows] for k, rows in v.items()}
        setattr(out, f, v)
    return out, {'saved': body.get('saved'), 'version': body.get('version')}


def _rows(table, width: int) -> dict[int, list[tuple]]:
    """{line: [{...}, {...}]} as the Lua parser gives it -> {line: [tuple of `width` values]}; short rows dropped."""
    out = {}
    for key, rows in (table or {}).items():
        if isinstance(rows, dict):
            rows = [rows[k] for k in sorted(rows)]
        good = []
        for r in rows or []:
            if isinstance(r, dict):
                r = [r[k] for k in sorted(r)]
            if isinstance(r, list) and len(r) >= width:
                good.append(tuple(r[:width]))
        out[int(key)] = good
    return out
