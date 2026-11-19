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
    src, _ = _load(data_dir / 'Sources.lua')
    out.limited_stock = src.get('LimitedStock', {}) or {}
    ven, _ = _load(data_dir / 'Vendor.lua')
    out.vendor_prices = ven.get('VendorPrices', {}) or {}
    rec, _ = _load(data_dir / 'Recipes.lua')
    out.recipe_data = rec.get('RecipeData', {}) or {}
    out.recipe_scrolls = rec.get('RecipeScrolls', {}) or {}
    return out
