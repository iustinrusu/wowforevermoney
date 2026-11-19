"""Read the generated data tables shipped with the SkillUpForever addon.

Used for recipe skill thresholds, trainer fees, limited-stock vendor items, and as an
independent cross-check of the recipes we derive from wago.tools.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from .lua import parse_assignments


@dataclass
class SkillUpData:
    thresholds: dict[int, list[int]] = field(default_factory=dict)     # recipe spell -> [orange, yellow, green, grey]
    trainer_fees: dict[int, list[int]] = field(default_factory=dict)   # recipe spell -> [fee copper, required skill]
    limited_stock: dict[int, dict[int, int]] = field(default_factory=dict)  # item -> {npc: stock}
    vendor_prices: dict[int, int] = field(default_factory=dict)        # item -> copper per unit
    recipe_data: dict[int, dict] = field(default_factory=dict)         # recipe spell -> {skillLine, reagents, output}
    recipe_scrolls: dict = field(default_factory=dict)
    source_build: str | None = None
    # filled by foreverrecipes.merged (the second recipe source): spells whose required skill is exact, the character
    # level a recipe needs, and the spells whose colours came from ForeverRecipes
    requirement_known: set = field(default_factory=set)
    level_required: dict[int, int] = field(default_factory=dict)
    from_forever_recipes: set = field(default_factory=set)
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
