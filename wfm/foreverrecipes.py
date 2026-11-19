"""Read the ForeverRecipes addon's data (the user installed it 2026-11-19): a second source of Forever recipe facts.

Its tables are generated from the Forever client (build 1.60.1.70938 in version 1.17.1) plus the author's own
observations and frozen Classic reference data (CMaNGOS), GPL-3.0; read here from the user's install, never copied.
What the app uses:
- skill colours [orange, yellow, green, grey] with `requirementKnown`: SkillUpForever stores 0/1 as the orange
  threshold when it doesn't know it (Cured Rugged Hide: the app guessed 185; ForeverRecipes says 225), and has no
  rogue Poisons at all; ForeverRecipes has both. SkillUpForever stays first where it knows; the two are compared on
  Data health.
- the character level a recipe needs (`levelRequired`, Poisons: Instant Poison II at 30)
- trainer fees and the skill the trainer asks for (Poisons: Instant Poison II costs 1g at Poisons 130)
Not used yet: its disenchant tables (Classic reference, "provisional estimates" in its own words), recipe drops and
sellers, Merchant's Favor items.
"""
from __future__ import annotations

import copy
import re
from dataclasses import dataclass, field
from pathlib import Path

from .lua import parse_assignments
from .skillup import SkillUpData


@dataclass
class ForeverRecipesData:
    recipes: dict[int, dict] = field(default_factory=dict)     # spell -> {skill_line, thresholds, reagents, product, count}
    meta: dict[int, dict] = field(default_factory=dict)        # spell -> {levelRequired, requirementKnown, ...}
    trainers: dict[int, list] = field(default_factory=dict)    # spell -> [(npc, copper, skill)]
    automatic: set[int] = field(default_factory=set)           # learned with the profession
    source_build: str | None = None


def load(data_dir: Path) -> ForeverRecipesData:
    out = ForeverRecipesData()
    rec_path, src_path = data_dir / 'Recipes.lua', data_dir / 'Sources.lua'
    if rec_path.exists():
        text = rec_path.read_text(encoding='utf-8', errors='replace')
        m = re.search(r'client build\s*([\d.]+)', text)
        out.source_build = m.group(1) if m else None
        d = parse_assignments(text)
        for spell, row in (d.get('Recipes') or {}).items():
            if not isinstance(row, list) or len(row) < 4:
                continue
            reag = row[2] or []
            product = row[3] or [0, 1]
            out.recipes[int(spell)] = {
                'skill_line': int(row[0]), 'thresholds': [int(x) for x in (row[1] or [])],
                'reagents': [(int(reag[i]), int(reag[i + 1])) for i in range(0, len(reag) - 1, 2)],
                'product': int(product[0]) if product else 0, 'count': float(product[1]) if len(product) > 1 else 1.0}
        out.meta = {int(k): v for k, v in (d.get('RecipeMeta') or {}).items() if isinstance(v, dict)}
    if src_path.exists():
        d = parse_assignments(src_path.read_text(encoding='utf-8', errors='replace'))
        for spell, rows in (d.get('Trainers') or {}).items():
            out.trainers[int(spell)] = [(int(r[0]), int(r[1]), int(r[2])) for r in rows or []
                                        if isinstance(r, list) and len(r) >= 3]
        out.automatic = {int(k) for k, v in (d.get('AutomaticRecipes') or {}).items() if v}
    return out


def merged(su: SkillUpData, fr: ForeverRecipesData | None) -> SkillUpData:
    """SkillUpForever's data with ForeverRecipes filling its holes (a new object; the inputs are not changed).
    - a recipe SkillUpForever lacks (Poisons) or whose orange it doesn't know (stored 0/1) takes ForeverRecipes'
      colours when ForeverRecipes knows the requirement; an orange of 0 (Poisons: no skill to craft once learned) is
      raised to the skill the trainer asks for, the real gate (Instant Poison II: Poisons 130)
    - trainer fees SkillUpForever lacks: the cheapest trainer
    - the character level a recipe needs
    Provenance: `requirement_known` (spells whose required skill is exact), `from_forever_recipes` (whose colours
    came from ForeverRecipes)."""
    out = copy.copy(su)
    out.thresholds = dict(su.thresholds)
    out.trainer_fees = dict(su.trainer_fees)
    out.requirement_known = {s for s, th in su.thresholds.items() if th and th[0] and th[0] > 1}
    out.level_required, out.from_forever_recipes = {}, set()
    if not fr:
        return out
    for spell, r in fr.recipes.items():
        meta = fr.meta.get(spell) or {}
        th = r['thresholds']
        trainers = fr.trainers.get(spell) or []
        if trainers and spell not in out.trainer_fees:
            cost, skill = min((c, s) for _, c, s in trainers)
            out.trainer_fees[spell] = [cost, skill]
        if meta.get('levelRequired'):
            out.level_required[spell] = int(meta['levelRequired'])
        if len(th) < 4 or not meta.get('requirementKnown') or not meta.get('thresholdsKnown', True):
            continue
        have = out.thresholds.get(spell)
        if have and have[0] and have[0] > 1:
            continue                                         # SkillUpForever knows it: it stays first
        orange = th[0]
        if orange <= 1 and trainers:
            orange = min(s for _, _, s in trainers)          # learnable from this skill on
        out.thresholds[spell] = [max(1, orange), th[1], th[2], th[3]]
        out.requirement_known.add(spell)
        out.from_forever_recipes.add(spell)
    return out


def compare(su: SkillUpData, fr: ForeverRecipesData | None) -> dict:
    """SkillUpForever vs ForeverRecipes on the recipes both have: how many agree on the colours, and the differences."""
    same, diff = 0, []
    for spell, th in su.thresholds.items():
        r = (fr.recipes.get(spell) if fr else None)
        if not r or len(r['thresholds']) < 4 or not th or len(th) < 4:
            continue
        a, b = [int(x) for x in th[1:4]], r['thresholds'][1:4]      # yellow, green, grey (orange is often unknown)
        if a == b:
            same += 1
        else:
            diff.append((spell, a, b))
    only_fr = sorted(set(fr.recipes) - set(su.thresholds)) if fr else []
    return {'both': same + len(diff), 'same': same, 'diff': diff, 'only_forever_recipes': only_fr}
